import 'dart:async';

import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../data/files/profile_recognition_image_store.dart';
import '../data/files/profile_paths.dart';
import '../data/files/resource_download_destination.dart';
import '../features/access/access_credential_vault.dart';
import '../network/api_error.dart';
import '../network/makolo_api_client.dart';
import '../presentation/possibilities/discovery_offline_store.dart';
import 'freshness.dart';
import 'sync_source.dart';

class SyncRoot {
  const SyncRoot(this.key, this.path);

  final String key;
  final String path;
}

class _SpaceAuthorityWithheld implements Exception {
  const _SpaceAuthorityWithheld();
}

class _SyncCoordinator {
  final Map<String, int> generations = {};
  final Map<String, int> discoveryEpochs = {};
  final Map<String, int> accessEpochs = {};
  final Map<String, int> personalResourceEpochs = {};
  final Map<String, int> spaceEpochs = {};
  final Map<String, int> spaceInventoryEpochs = {};
}

class _InFlightSourcePull {
  const _InFlightSourcePull({
    required this.path,
    required this.projectionKind,
    required this.generation,
    required this.future,
  });

  final String path;
  final String projectionKind;
  final int generation;
  final Future<void> future;
}

class SyncEngine {
  static final Expando<_SyncCoordinator> _coordinators =
      Expando<_SyncCoordinator>('sync-per-database');

  SyncEngine({
    required this.api,
    required this.store,
    required this.database,
    required this.profileId,
  }) {
    if (profileId.isEmpty ||
        store.profileId != profileId ||
        !identical(store.database, database)) {
      throw ArgumentError('SyncEngine must use one matching ProfileStore');
    }
  }

  final MakoloApiClient api;
  final ProfileStore store;
  final MakoloDatabase database;
  final String profileId;

  // Owner sources registered by the composition root, not by a widget.
  // Registrations are ephemeral contracts; source results remain durable.
  final Map<String, SyncSourceDefinition> _preparedSources = {};
  final Map<String, Future<void> Function()> _preparedAcquirers = {};
  final Map<String, DateTime> _lastPreparedAttempt = {};
  final Map<String, _InFlightSourcePull> _inFlightSourcePulls = {};

  /// Opt in stable owner sources for bounded proactive acquisition.
  /// Never prefetch signed continuation URLs or an unverified Space context.
  void registerPreparedSource(
    SyncSourceDefinition source, {
    Future<void> Function()? acquire,
  }) {
    if (!source.actorScope.isPersonal ||
        Uri.parse(source.path).queryParameters.containsKey('continuation')) {
      throw ArgumentError('Prepared source requires a stable personal scope');
    }
    final previous = _preparedSources[source.sourceKey];
    if (previous != null &&
        (previous.path != source.path ||
            previous.projectionKind != source.projectionKind ||
            previous.resourceKey != source.resourceKey)) {
      throw ArgumentError('Source key already identifies another owner route');
    }
    _preparedSources[source.sourceKey] = source;
    if (acquire != null) {
      _preparedAcquirers[source.sourceKey] = acquire;
    }
  }

  /// Reconnect is a new transport opportunity. It does not clear an owner
  /// revocation or grant authority; only the in-memory retry delay resets.
  void onConnectivityRestored() => _lastPreparedAttempt.clear();

  /// Progressive working-set acquisition. Sources are checked for durable
  /// freshness, bounded by a request budget, and resumed on later cycles.
  /// A transport failure stops the batch; a scoped 403/404 is not a global
  /// connectivity failure. Never treat old local observations as empty.
  Future<bool> refreshPreparedSources({int maxRequests = 7}) async {
    if (maxRequests < 1) {
      throw ArgumentError.value(maxRequests, 'maxRequests');
    }
    if (!_active) return false;
    var requested = 0;
    for (final source in _preparedSources.values) {
      if (!_active || requested >= maxRequests) break;
      final state =
          await (database.select(database.syncSources)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.sourceKey.equals(source.sourceKey),
              ))
              .getSingleOrNull();
      // A confirmed owner denial is not retried automatically on every
      // app resume. A later owner event or explicit user request can reopen it.
      if (state?.invalidated == true &&
          const {
            'permission_denied',
            'not_found',
          }.contains(state?.lastErrorCode)) {
        continue;
      }
      final snapshot = await store.readProjection(
        source.projectionKind,
        resourceKey: source.resourceKey,
      );
      final now = DateTime.now().toUtc();
      final refreshAfter =
          source.freshnessPolicy.refreshRecommendedAfter ??
          const Duration(minutes: 30);
      final lastSuccessAt = state?.lastSuccessAt?.toUtc();
      final due =
          state == null ||
          state.invalidated ||
          snapshot == null ||
          lastSuccessAt == null ||
          lastSuccessAt.isAfter(now) ||
          now.difference(lastSuccessAt) >= refreshAfter;
      if (!due) continue;
      final attemptedAt = _lastPreparedAttempt[source.sourceKey];
      // A manual clock rollback must not suppress acquisitions until the
      // device clock eventually catches an old in-memory attempt timestamp.
      if (attemptedAt != null &&
          !attemptedAt.isAfter(now) &&
          now.difference(attemptedAt) < const Duration(seconds: 30)) {
        continue;
      }
      _lastPreparedAttempt[source.sourceKey] = now;
      requested++;
      try {
        final acquire = _preparedAcquirers[source.sourceKey];
        if (acquire == null) {
          await pullSource(source);
        } else {
          // Some owners do additional local maintenance after their pull,
          // e.g. Discovery preview indexing or Space context reconciliation.
          await acquire();
          // Repositories using refreshSource may handle transport failures
          // internally. Consult the durable owner state before reporting
          // their acquisition as successful.
          final completed =
              await (database.select(database.syncSources)..where(
                    (row) =>
                        row.profileId.equals(profileId) &
                        row.sourceKey.equals(source.sourceKey),
                  ))
                  .getSingleOrNull();
          final errorCode = completed?.lastErrorCode;
          if (errorCode != null) {
            if (completed != null &&
                completed.invalidated &&
                const {'permission_denied', 'not_found'}.contains(errorCode)) {
              continue;
            }
            return false;
          }
        }
      } on MakoloApiError catch (error) {
        if (error.statusCode == 401) rethrow;
        if (error.statusCode == 403 || error.statusCode == 404) continue;
        return false;
      } on Object {
        // A failed owner pull already records its source-specific error.
        // Do not storm the rest of the working set with more failed requests.
        return false;
      }
    }
    return true;
  }

  // Shared among SyncEngine instances bound to one SQLite connection.
  // Separate runtimes cannot resurrect a previously withdrawn Profile fact.
  _SyncCoordinator get _coordinator =>
      _coordinators[database] ??= _SyncCoordinator();
  String _scopeKey(SyncSourceDefinition source) =>
      '$profileId|${source.actorScope.stableKey}|${source.sourceKey}';
  int get _discoveryRevocationEpoch =>
      _coordinator.discoveryEpochs[profileId] ?? 0;
  int get _accessRevocationEpoch => _coordinator.accessEpochs[profileId] ?? 0;
  int get _personalResourceRevocationEpoch =>
      _coordinator.personalResourceEpochs[profileId] ?? 0;
  int _spaceEpoch(String spaceId) =>
      _coordinator.spaceEpochs['$profileId|$spaceId'] ?? 0;
  int get _spaceInventoryEpoch =>
      _coordinator.spaceInventoryEpochs[profileId] ?? 0;
  static bool _deniedOwnerState(String? code) =>
      code == 'permission_denied' || code == 'not_found';

  Future<bool> _spaceAuthorityWithdrawn(String spaceId) async {
    final encoded = Uri.encodeComponent(spaceId);
    final inventory =
        await (database.select(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals('space.inventory'),
            ))
            .getSingleOrNull();
    if (inventory?.invalidated == true &&
        _deniedOwnerState(inventory?.lastErrorCode)) {
      return true;
    }
    final workspace =
        await (database.select(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals('space:$encoded:workspace'),
            ))
            .getSingleOrNull();
    return workspace?.invalidated == true &&
        _deniedOwnerState(workspace?.lastErrorCode);
  }

  Future<bool> _inventoryAuthorityWithdrawn() async {
    final inventory =
        await (database.select(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals('space.inventory'),
            ))
            .getSingleOrNull();
    return inventory?.invalidated == true &&
        _deniedOwnerState(inventory?.lastErrorCode);
  }

  bool _active = true;
  bool get isActive => _active;

  /// Stop all in-flight acquisitions on account/runtime replacement.
  /// Never erase durable user-owned offline knowledge on logout alone.
  void deactivate() {
    // Old requests fail their own isCurrent guard; leave newly constructed
    // workers for the same Profile free to complete after runtime rotation.
    _active = false;
  }

  static bool _isDiscoveryRelated(SyncSourceDefinition source) =>
      source.owner == 'Discovery' ||
      source.projectionKind == 'activity.detail' ||
      source.projectionKind == 'occurrence.detail';

  static const _personalResourceDetailKinds = <String>{
    'personal.resource.detail',
    'personal.proof.detail',
    'personal.title.detail',
  };

  static const _personalResourceCollectionKinds = <String>{
    'personal.me.resources',
    'personal.proofs',
    'personal.titles',
  };

  static bool _isPersonalResourceProjection(String kind) =>
      kind == 'personal.me' ||
      _personalResourceDetailKinds.contains(kind) ||
      _personalResourceCollectionKinds.contains(kind);

  static String? _resourceFamilyForDetail(String kind) => switch (kind) {
    'personal.resource.detail' => 'documents',
    'personal.proof.detail' => 'proofs',
    'personal.title.detail' => 'credentials',
    _ => null,
  };

  static Map<String, dynamic>? _resourceMap(Object? value) {
    if (value is Map<String, dynamic>) {
      return Map<String, dynamic>.from(value);
    }
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    return null;
  }

  Future<Map<String, Set<String>>> _deniedPersonalResourceIds() async {
    final denied = <String, Set<String>>{
      'documents': <String>{},
      'proofs': <String>{},
      'credentials': <String>{},
    };
    final rows = await (database.select(
      database.syncSources,
    )..where((row) => row.profileId.equals(profileId))).get();
    for (final row in rows) {
      if (!row.invalidated || !_deniedOwnerState(row.lastErrorCode)) continue;
      final key = row.sourceKey;
      if (key.startsWith('resource:')) {
        denied['documents']!.add(key.substring('resource:'.length));
      } else if (key.startsWith('trust:proofs:')) {
        denied['proofs']!.add(key.substring('trust:proofs:'.length));
      } else if (key.startsWith('trust:titles:')) {
        denied['credentials']!.add(key.substring('trust:titles:'.length));
      }
    }
    return denied;
  }

  Map<String, dynamic> _filterResourceFamilyPayload(
    Map<String, dynamic> payload,
    String family,
    Set<String> denied,
  ) {
    if (denied.isEmpty) return payload;
    final familyPayload = _resourceMap(payload[family]);
    final items = familyPayload?['items'];
    if (familyPayload == null || items is! List) return payload;
    final retained = items
        .where((row) {
          if (row is! Map) return true;
          final id = row['id']?.toString();
          return id == null || !denied.contains(id);
        })
        .toList(growable: false);
    if (retained.length == items.length) return payload;
    final removed = items.length - retained.length;
    final updatedFamily = <String, dynamic>{
      ...familyPayload,
      'items': retained,
    };
    final count = familyPayload['count'];
    if (count is int) {
      updatedFamily['count'] = (count - removed).clamp(0, count).toInt();
    }
    final page = _resourceMap(familyPayload['page']);
    if (page != null) {
      final pageCount = page['count'];
      updatedFamily['page'] = {
        ...page,
        if (pageCount is int)
          'count': (pageCount - removed).clamp(0, pageCount).toInt(),
      };
    }
    return {...payload, family: updatedFamily};
  }

  Map<String, dynamic> _filterFlatResourcePayload(
    Map<String, dynamic> payload,
    Set<String> denied,
  ) {
    if (denied.isEmpty) return payload;
    final items = payload['items'];
    if (items is! List) return payload;
    final retained = items
        .where((row) {
          if (row is! Map) return true;
          final id = row['id']?.toString();
          return id == null || !denied.contains(id);
        })
        .toList(growable: false);
    if (retained.length == items.length) return payload;
    final removed = items.length - retained.length;
    final updated = <String, dynamic>{...payload, 'items': retained};
    final count = payload['count'];
    if (count is int) {
      updated['count'] = (count - removed).clamp(0, count).toInt();
    }
    final page = _resourceMap(payload['page']);
    if (page != null) {
      final pageCount = page['count'];
      updated['page'] = {
        ...page,
        if (pageCount is int)
          'count': (pageCount - removed).clamp(0, pageCount).toInt(),
      };
    }
    return updated;
  }

  Future<AcquiredProjection> _withoutRevokedPersonalResources(
    AcquiredProjection acquired,
    String projectionKind,
  ) async {
    if (!_isPersonalResourceProjection(projectionKind) ||
        _personalResourceDetailKinds.contains(projectionKind)) {
      return acquired;
    }
    final denied = await _deniedPersonalResourceIds();
    var payload = Map<String, dynamic>.from(acquired.payload);
    if (projectionKind == 'personal.proofs') {
      payload = _filterFlatResourcePayload(payload, denied['proofs']!);
    } else if (projectionKind == 'personal.titles') {
      payload = _filterFlatResourcePayload(payload, denied['credentials']!);
    } else if (projectionKind == 'personal.me.resources') {
      for (final family in const ['documents', 'proofs', 'credentials']) {
        payload = _filterResourceFamilyPayload(
          payload,
          family,
          denied[family]!,
        );
      }
    } else if (projectionKind == 'personal.me') {
      final resources = _resourceMap(payload['resources']);
      if (resources != null) {
        var filtered = resources;
        for (final family in const ['documents', 'proofs', 'credentials']) {
          filtered = _filterResourceFamilyPayload(
            filtered,
            family,
            denied[family]!,
          );
        }
        payload['resources'] = filtered;
      }
    }
    return AcquiredProjection(
      schemaVersion: acquired.schemaVersion,
      payload: payload,
      sourceGeneratedAt: acquired.sourceGeneratedAt,
      sourceUpdatedAt: acquired.sourceUpdatedAt,
      freshUntil: acquired.freshUntil,
      expiresAt: acquired.expiresAt,
    );
  }

  Future<void> _storeProjectionPreservingMetadata(
    StoredProjection projection,
    Map<String, dynamic> payload,
  ) => store.putProjection(
    kind: projection.kind,
    resourceKey: projection.resourceKey,
    schemaVersion: projection.schemaVersion,
    payload: payload,
    receivedAt: projection.receivedAt,
    sourceGeneratedAt: projection.sourceGeneratedAt,
    sourceUpdatedAt: projection.sourceUpdatedAt,
    lastVerifiedOnlineAt: projection.lastVerifiedOnlineAt,
    freshUntil: projection.freshUntil,
    expiresAt: projection.expiresAt,
    freshnessPolicyId: projection.freshnessPolicyId,
  );

  Future<void> _redactDeniedPersonalResource(
    SyncSourceDefinition source,
  ) async {
    final family = _resourceFamilyForDetail(source.projectionKind);
    if (family == null || source.resourceKey.isEmpty) return;
    final deniedId = source.resourceKey;

    for (final page in await store.readProjections('personal.me.resources')) {
      final updated = _filterResourceFamilyPayload(page.payload, family, {
        deniedId,
      });
      if (!identical(updated, page.payload)) {
        await _storeProjectionPreservingMetadata(page, updated);
      }
    }

    final root = await store.readProjection('personal.me');
    if (root != null) {
      final resources = _resourceMap(root.payload['resources']);
      if (resources != null) {
        final updatedResources = _filterResourceFamilyPayload(
          resources,
          family,
          {deniedId},
        );
        if (!identical(updatedResources, resources)) {
          await _storeProjectionPreservingMetadata(root, {
            ...root.payload,
            'resources': updatedResources,
          });
        }
      }
    }

    final dedicatedKind = switch (family) {
      'proofs' => 'personal.proofs',
      'credentials' => 'personal.titles',
      _ => null,
    };
    if (dedicatedKind != null) {
      for (final page in await store.readProjections(dedicatedKind)) {
        final updated = _filterFlatResourcePayload(page.payload, {deniedId});
        if (!identical(updated, page.payload)) {
          await _storeProjectionPreservingMetadata(page, updated);
        }
      }
    }
  }

  bool _samePersonalResourceCollectionFamily(
    String projectionKind,
    String sourceKey,
  ) {
    return switch (projectionKind) {
      'personal.me.resources' => sourceKey.startsWith('resources:'),
      'personal.proofs' => sourceKey.startsWith('trust:proofs%7C'),
      'personal.titles' => sourceKey.startsWith('trust:titles%7C'),
      _ => false,
    };
  }

  Future<void> _withdrawPersonalResourceCollectionFamily(
    SyncSourceDefinition source,
    String code,
  ) async {
    if (!_personalResourceCollectionKinds.contains(source.projectionKind)) {
      return;
    }
    await store.deleteProjectionsOfKind(source.projectionKind);
    final coordinator = _coordinator;
    final activePrefix = '$profileId|personal|';
    for (final activeKey in coordinator.generations.keys.toList()) {
      if (!activeKey.startsWith(activePrefix)) continue;
      final sourceKey = activeKey.substring(activePrefix.length);
      if (_samePersonalResourceCollectionFamily(
        source.projectionKind,
        sourceKey,
      )) {
        coordinator.generations[activeKey] =
            (coordinator.generations[activeKey] ?? 0) + 1;
      }
    }
    final rows = await (database.select(
      database.syncSources,
    )..where((row) => row.profileId.equals(profileId))).get();
    for (final row in rows) {
      if (!_samePersonalResourceCollectionFamily(
        source.projectionKind,
        row.sourceKey,
      )) {
        continue;
      }
      await (database.update(database.syncSources)..where(
            (item) =>
                item.profileId.equals(profileId) &
                item.sourceKey.equals(row.sourceKey),
          ))
          .write(
            SyncSourcesCompanion(
              invalidated: const Value(true),
              lastErrorCode: Value(code),
            ),
          );
    }
  }

  static const _discoveryDerivedKinds = <String>[
    'discovery.items',
    'discovery.map',
    'discovery.presented-window',
    'discovery.unseen-reserve',
    'discovery.item',
    'discovery.activity-preview',
    'discovery.occurrence-preview',
    'discovery.watch-results',
    'discovery.presentation-position',
  ];

  static const roots = [
    SyncRoot('personal.now', 'api/v1/me/now/'),
    SyncRoot('personal.ongoing', 'api/v1/me/ongoing/'),
    SyncRoot('personal.me', 'api/v1/me/'),
  ];

  static const interoperabilityRoot = SyncRoot(
    'personal.interoperability',
    'api/v1/me/interoperability/',
  );

  SyncSourceDefinition _rootSource(SyncRoot root) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: root.key,
      owner: 'Profile',
      path: root.path,
      projectionKind: root.key,
      freshnessPolicy: const FreshnessPolicy(id: 'swr'),
    );
  }

  SyncSourceDefinition get _interoperabilitySource => SyncSourceDefinition(
    sourceKey: interoperabilityRoot.key,
    owner: 'Interoperability',
    path: interoperabilityRoot.path,
    projectionKind: interoperabilityRoot.key,
    category: SyncSourceCategory.root,
    freshnessPolicy: const FreshnessPolicy(id: 'contextual'),
    parser: (response) {
      final payload = response.jsonObject();
      if (payload['schema_version'] != 'z16.v1' ||
          payload['context'] != 'profile') {
        throw const FormatException(
          'Expected z16.v1 Profile interoperability projection.',
        );
      }
      return AcquiredProjection(schemaVersion: 1, payload: payload);
    },
    applier: applyProjectionSnapshot,
  );

  Future<void> bootstrap() async {
    await store.purgeExpiredProjections();
    for (final root in roots) {
      await pull(root);
    }
    await pullInteroperability();
  }

  Future<bool> refreshRoots() async {
    await store.purgeExpiredProjections();
    // Profile projections are independent: a slow Now request cannot delay
    // Ongoing or Me. Record partial failures without discarding local facts.
    final results = await Future.wait([
      for (final root in roots) _refreshSourceStatus(_rootSource(root)),
    ]);
    final interoperabilityReady = await _refreshSourceStatus(
      _interoperabilitySource,
    );
    // A transport failure must not be reported as a successful refresh just
    // because each owner source kept its existing local snapshot.
    return results.every((success) => success) && interoperabilityReady;
  }

  /// Reconcile the canonical personal Me root after an owner-confirmed
  /// mutation. Every feature uses the same source contract and revocation
  /// protection; no widget should write its own competing root snapshot.
  Future<bool> refreshPersonalMe() =>
      _refreshSourceStatus(_rootSource(roots[2]));

  Future<void> refreshSource(SyncSourceDefinition source) async {
    await _refreshSourceStatus(source);
  }

  Future<bool> _refreshSourceStatus(SyncSourceDefinition source) async {
    try {
      await pullSource(source);
      return true;
    } on MakoloApiError catch (error) {
      if (error.statusCode == 401) rethrow;
      return false;
    } on Object {
      // The failure is recorded by pullSource. Existing local data is kept.
      return false;
    }
  }

  Future<void> pull(SyncRoot root) => pullSource(_rootSource(root));

  Future<void> pullInteroperability() => pullSource(_interoperabilitySource);

  /// Share a pending owner read when its scope, route and generation match.
  /// Invalidation or an owner denial increments the generation, so the next
  /// acquisition cannot join an obsolete request.
  Future<void> pullSource(SyncSourceDefinition source) {
    if (!_active) return Future<void>.value();
    final key = _scopeKey(source);
    final existing = _inFlightSourcePulls[key];
    if (existing != null &&
        existing.path == source.path &&
        existing.projectionKind == source.projectionKind &&
        existing.generation == _coordinator.generations[key]) {
      return existing.future;
    }
    final request = _pullSourceOnce(source);
    final pending = _InFlightSourcePull(
      path: source.path,
      projectionKind: source.projectionKind,
      generation: _coordinator.generations[key]!,
      future: request,
    );
    _inFlightSourcePulls[key] = pending;
    // Register both completion paths: never create an unhandled secondary
    // failed Future merely to perform map cleanup.
    void cleanup() {
      if (identical(_inFlightSourcePulls[key], pending)) {
        _inFlightSourcePulls.remove(key);
      }
    }

    unawaited(
      request.then(
        (_) => cleanup(),
        onError: (Object _, StackTrace _) {
          cleanup();
        },
      ),
    );
    return request;
  }

  Future<void> _pullSourceOnce(SyncSourceDefinition source) async {
    final key = _scopeKey(source);
    final coordinator = _coordinator;
    final generation = (coordinator.generations[key] ?? 0) + 1;
    coordinator.generations[key] = generation;
    final epoch = _discoveryRevocationEpoch;
    final accessEpoch = _accessRevocationEpoch;
    final personalResourceEpoch = _personalResourceRevocationEpoch;
    final inventoryEpoch = _spaceInventoryEpoch;
    final spaceId = source.actorScope.spaceId;
    final spaceEpoch = spaceId == null ? 0 : _spaceEpoch(spaceId);
    bool isCurrent() =>
        _active &&
        coordinator.generations[key] == generation &&
        (!_isDiscoveryRelated(source) || _discoveryRevocationEpoch == epoch) &&
        (!source.projectionKind.startsWith('personal.access') ||
            _accessRevocationEpoch == accessEpoch) &&
        (!_isPersonalResourceProjection(source.projectionKind) ||
            _personalResourceRevocationEpoch == personalResourceEpoch) &&
        (source.projectionKind != 'space.inventory' ||
            _spaceInventoryEpoch == inventoryEpoch) &&
        (spaceId == null ||
            (_spaceEpoch(spaceId) == spaceEpoch &&
                _spaceInventoryEpoch == inventoryEpoch));
    try {
      if (spaceId != null &&
          (source.projectionKind != 'space.workspace' ||
              await _inventoryAuthorityWithdrawn()) &&
          await _spaceAuthorityWithdrawn(spaceId)) {
        throw const _SpaceAuthorityWithheld();
      }
      final response = await api.get(source.path);
      if (!isCurrent()) return;
      final acquired = source.parser(response);
      if (!isCurrent()) return;
      // The owner sometimes exposes a Profile actor. If present, its
      // identity must match the authenticated local storage boundary.
      if (source.actorScope.isPersonal && source.owner == 'Profile') {
        final actor = acquired.payload['actor'];
        if (actor is Map &&
            actor['id'] != null &&
            actor['id'].toString() != profileId) {
          throw const FormatException('Owner Profile mismatch');
        }
      }

      await database.transaction(() async {
        if (spaceId != null &&
            (source.projectionKind != 'space.workspace' ||
                await _inventoryAuthorityWithdrawn()) &&
            await _spaceAuthorityWithdrawn(spaceId)) {
          return; // A denied Space cannot be restored by another view.
        }
        // Across engine instances and process-resumed requests, a response
        // with an older owner generation cannot replace newer local facts.
        final observed =
            await (database.select(database.syncSources)..where(
                  (row) =>
                      row.profileId.equals(profileId) &
                      row.sourceKey.equals(source.sourceKey),
                ))
                .getSingleOrNull();
        if (observed?.generatedAtSeen != null &&
            (acquired.sourceGeneratedAt == null ||
                acquired.sourceGeneratedAt!.isBefore(
                  observed!.generatedAtSeen!,
                ))) {
          // A response without newer provenance cannot overwrite a locally
          // known, owner-timestamped observation.
          return;
        }
        if (!isCurrent()) return;
        var approved = source.projectionKind == 'personal.accesses'
            ? await _withoutRevokedAccessRows(acquired)
            : source.projectionKind == 'space.inventory'
            ? await _withoutRevokedSpaceRows(acquired)
            : acquired;
        approved = await _withoutRevokedPersonalResources(
          approved,
          source.projectionKind,
        );
        await source.applier(
          SyncApplyContext(
            database: database,
            store: store,
            profileId: profileId,
            source: source,
          ),
          approved,
        );
        await database
            .into(database.syncSources)
            .insertOnConflictUpdate(
              SyncSourcesCompanion.insert(
                profileId: profileId,
                sourceKey: source.sourceKey,
                route: source.path,
                schemaVersionSeen: Value(acquired.schemaVersion),
                lastSuccessAt: Value(DateTime.now().toUtc()),
                generatedAtSeen: Value(acquired.sourceGeneratedAt),
                invalidated: const Value(false),
                lastErrorCode: const Value(null),
              ),
            );
      });
    } on _SpaceAuthorityWithheld {
      // A durable owner tombstone is not a transport failure. Keep its
      // authorization status intact until a canonical owner revalidation.
      rethrow;
    } on TimeoutException {
      if (isCurrent()) await _recordFailure(source, 'timeout');
      rethrow;
    } on MakoloApiError catch (error) {
      if (isCurrent()) {
        if (error.statusCode == 404 &&
            source.projectionKind == 'objective.organizer.collection') {
          // An authenticated collection is either populated or empty (HTTP
          // 200). A 404 here points to a missing/mismatched deployment route,
          // not proof that this Profile lost authority. Earlier clients
          // treated it as a revocation and removed an otherwise valid cache.
          await _recordOrganizerEndpointUnavailable(source);
        } else if (error.statusCode == 403 || error.statusCode == 404) {
          // Only owner-scoped refusals are durable authorization tombstones.
          await _recordScopedUnavailable(
            source,
            error.statusCode == 403 ? 'permission_denied' : 'not_found',
          );
        } else {
          final cursorRejected =
              source.projectionKind == 'discovery.items' &&
              error.statusCode == 400 &&
              Uri.parse(source.path).queryParameters
                  .containsKey('continuation');
          await _recordFailure(
            source,
            cursorRejected ? 'continuation_rejected' : error.code,
          );
        }
      }
      rethrow;
    } on FormatException {
      if (isCurrent()) await _recordFailure(source, 'contract_error');
      rethrow;
    } on MakoloTransportError catch (error) {
      if (isCurrent()) await _recordFailure(source, error.code);
      rethrow;
    } on Object {
      if (isCurrent()) await _recordFailure(source, 'transport_error');
      rethrow;
    }
  }

  Future<void> invalidate(SyncSourceDefinition source) async {
    _lastPreparedAttempt.remove(source.sourceKey);
    final key = _scopeKey(source);
    final coordinator = _coordinator;
    coordinator.generations[key] = (coordinator.generations[key] ?? 0) + 1;
    await _ensureSource(source);
    final existing =
        await (database.select(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals(source.sourceKey),
            ))
            .getSingleOrNull();
    // Invalidating a source marks it due for refresh; it must not erase a
    // confirmed Space authority withdrawal before workspace/inventory
    // has actually been revalidated by its owner.
    final protectedDenial =
        (source.projectionKind == 'space.workspace' ||
            source.projectionKind == 'space.inventory' ||
            source.projectionKind == 'personal.access.detail' ||
            source.projectionKind == 'personal.accesses' ||
            _personalResourceDetailKinds.contains(source.projectionKind) ||
            _personalResourceCollectionKinds.contains(source.projectionKind)) &&
        existing?.invalidated == true &&
        _deniedOwnerState(existing?.lastErrorCode);
    await (database.update(database.syncSources)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals(source.sourceKey),
        ))
        .write(
          SyncSourcesCompanion(
            invalidated: const Value(true),
            lastErrorCode: protectedDenial
                ? Value(existing?.lastErrorCode)
                : const Value(null),
          ),
        );
  }

  /// Use only on an explicit owner 403/404, never on a timeout or after
  /// a local mutation. It withdraws derived material atomically.
  Future<void> revoke(
    SyncSourceDefinition source, {
    String code = 'permission_denied',
  }) {
    if (code != 'permission_denied' && code != 'not_found') {
      throw ArgumentError.value(code, 'code');
    }
    return _recordScopedUnavailable(source, code);
  }

  Future<void> _recordOrganizerEndpointUnavailable(
    SyncSourceDefinition source,
  ) async {
    // The previous implementation may have persisted a false 404 tombstone.
    // Migrate only that legacy state, never an explicit 403 permission denial.
    // Keep any legitimately acquired collection instead of deleting it.
    await database.transaction(() async {
      await _ensureSource(source);
      final observed =
          await (database.select(database.syncSources)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.sourceKey.equals(source.sourceKey),
              ))
              .getSingleOrNull();
      if (observed?.invalidated == true &&
          observed?.lastErrorCode == 'permission_denied') {
        return;
      }
      await (database.update(database.syncSources)..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.sourceKey.equals(source.sourceKey),
          ))
          .write(
            const SyncSourcesCompanion(
              invalidated: Value(false),
              lastErrorCode: Value('endpoint_unavailable'),
            ),
          );
    });
  }

  Future<void> _recordScopedUnavailable(
    SyncSourceDefinition source,
    String code,
  ) async {
    // Invalidate all concurrently in-flight Discovery readers. A successful
    // response to another request, started before this denial, cannot
    // rehydrate a derived collection after the withdrawal committed.
    final coordinator = _coordinator;
    final key = _scopeKey(source);
    coordinator.generations[key] = (coordinator.generations[key] ?? 0) + 1;
    if (_isDiscoveryRelated(source)) {
      coordinator.discoveryEpochs[profileId] = _discoveryRevocationEpoch + 1;
    }
    if (source.projectionKind == 'personal.access.detail' ||
        source.projectionKind == 'personal.accesses') {
      coordinator.accessEpochs[profileId] = _accessRevocationEpoch + 1;
    }
    if (_personalResourceDetailKinds.contains(source.projectionKind) ||
        _personalResourceCollectionKinds.contains(source.projectionKind)) {
      coordinator.personalResourceEpochs[profileId] =
          _personalResourceRevocationEpoch + 1;
    }
    final deniedSpace = source.projectionKind == 'space.workspace'
        ? source.actorScope.spaceId
        : null;
    final deniedInventory = source.projectionKind == 'space.inventory';
    if (deniedSpace != null || deniedInventory) {
      coordinator.spaceInventoryEpochs[profileId] = _spaceInventoryEpoch + 1;
      if (deniedSpace != null) {
        coordinator.spaceEpochs['$profileId|$deniedSpace'] =
            _spaceEpoch(deniedSpace) + 1;
      }
      // In-flight requests for this Space, including operations and other
      // repository instances, are rejected before they can commit.
      for (final activeKey in coordinator.generations.keys.toList()) {
        final sameProfile = activeKey.startsWith('$profileId|');
        final sameSpace =
            deniedSpace == null ||
            activeKey.startsWith('$profileId|space:$deniedSpace');
        if (sameProfile && sameSpace) {
          coordinator.generations[activeKey] =
              (coordinator.generations[activeKey] ?? 0) + 1;
        }
      }
    }
    // A denied History owner invalidates its previously received search
    // views as a family. Older in-flight pages cannot restore them.
    // A denied Jour J invalidates the sibling Live projection for exactly the
    // same Profile, actor and Occurrence. Live's own 404 is not reciprocal:
    // Live may simply be disabled while Jour J remains authorized.
    final deniedOccurrenceDayOf =
        source.projectionKind == 'occurrence.experience.day_of';
    final siblingLiveSourceKey = deniedOccurrenceDayOf
        ? source.actorScope.isSpace
              ? 'space-live-experience:${source.actorScope.spaceId}:${source.resourceKey.split('|').last}'
              : 'live-experience:${source.resourceKey}'
        : null;
    if (siblingLiveSourceKey != null) {
      final siblingKey =
          '$profileId|${source.actorScope.stableKey}|$siblingLiveSourceKey';
      coordinator.generations[siblingKey] =
          (coordinator.generations[siblingKey] ?? 0) + 1;
    }
    if (source.owner == 'ProfileHistory') {
      for (final key
          in coordinator.generations.keys
              .where((key) => key.startsWith('$profileId|personal|history:'))
              .toList()) {
        coordinator.generations[key] = (coordinator.generations[key] ?? 0) + 1;
      }
    }
    await database.transaction(() async {
      await store.deleteProjection(
        source.projectionKind,
        resourceKey: source.resourceKey,
      );
      if (siblingLiveSourceKey != null) {
        // Tombstone the companion before cold-start or in-flight readers can
        // present information that the day-of owner has just withdrawn.
        await store.deleteProjection(
          'occurrence.experience.live',
          resourceKey: source.resourceKey,
        );
        await (database.update(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals(siblingLiveSourceKey),
            ))
            .write(
              SyncSourcesCompanion(
                invalidated: const Value(true),
                lastErrorCode: Value(code),
              ),
            );
      }
      if (deniedSpace != null || deniedInventory) {
        await _withdrawSpaceFacts(spaceId: deniedSpace, code: code);
      }
      if (source.projectionKind == 'personal.access.detail') {
        await _redactAccessFromCollections(source.resourceKey);
      }
      if (source.projectionKind == 'personal.accesses') {
        await _withdrawAccessCollectionRelationship(source, code);
      }
      if (_personalResourceDetailKinds.contains(source.projectionKind)) {
        await _redactDeniedPersonalResource(source);
      }
      if (_personalResourceCollectionKinds.contains(source.projectionKind)) {
        await _withdrawPersonalResourceCollectionFamily(source, code);
      }
      // The field, map, N2 and previews are a composition of owner facts.
      // Once any such owner explicitly refuses access, retaining a copy
      // elsewhere is a privacy leak. Transport errors never enter this path.
      if (_isDiscoveryRelated(source)) {
        for (final kind in _discoveryDerivedKinds) {
          await store.deleteProjectionsOfKind(kind);
        }
        if (source.projectionKind == 'discovery.watches') {
          await store.deleteProjectionsOfKind('discovery.watches');
        }
        // Every saved cursor in this Profile is now unusable. A retained
        // source row must not claim its deleted snapshot is still current.
        await (database.update(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.like('discovery%'),
            ))
            .write(const SyncSourcesCompanion(invalidated: Value(true)));
      }
      // Invalidate derived read models in the same SQLite transaction as
      // the owner tombstone, so cold-start readers never see a partial purge.
      if (source.projectionKind == 'personal.now') {
        await store.deleteProjection('personal.now.continuation');
      }
      if (source.projectionKind == 'personal.ongoing') {
        await store.deleteProjection('personal.ongoing.continuation');
      }
      if (source.projectionKind == 'personal.me') {
        await store.deleteProjectionsOfKind('personal.me.passport');
      }
      if (source.owner == 'ProfileHistory') {
        await store.deleteProjectionsOfKind('personal.history');
        await store.deleteProjectionsOfKind('personal.history.search');
        await (database.update(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.like('history:%'),
            ))
            .write(
              SyncSourcesCompanion(
                invalidated: const Value(true),
                lastErrorCode: Value(code),
              ),
            );
      }
      await _ensureSource(source);
      await (database.update(database.syncSources)..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.sourceKey.equals(source.sourceKey),
          ))
          .write(
            SyncSourcesCompanion(
              invalidated: const Value(true),
              lastErrorCode: Value(code),
            ),
          );
    });
    // Owner denial also withdraws automatic published-recognition bytes.
    // Explicit Reader retention stays user-owned and independent.
    if (_isDiscoveryRelated(source)) {
      try {
        await const DiscoveryOfflineStore().purgeAutomaticRecognition();
      } on Object {
        // Recognition cache cleanup is best effort after SQLite withdrawal.
      }
      try {
        await DiscoveryOfflineStore(profileId: profileId).purgePrivateReader();
      } on Object {
        // A failure in one filesystem surface must not skip the other.
      }
    }
    // A source refusal withdraws only its retained private representation.
    // Explicitly exported documents outside the app remain user-owned.
    if (source.projectionKind == 'personal.resource.detail') {
      try {
        await removeLocallyRetainedResourceVersions(
          profileId: profileId,
          assetId: source.resourceKey,
        );
      } on Object {
        // SQL denial remains binding even if cleanup must be retried.
      }
    } else if (source.projectionKind == 'personal.me.resources') {
      try {
        await removeAllLocallyRetainedResources(profileId);
      } on Object {
        // No credential or document bytes are written into projections.
      }
    }
    if (source.projectionKind == 'personal.access.detail' ||
        (source.projectionKind == 'personal.accesses' &&
            source.resourceKey.startsWith('beneficiary:'))) {
      try {
        final vault = SecureAccessCredentialVault();
        if (source.projectionKind == 'personal.access.detail') {
          await vault.delete(profileId, source.resourceKey);
        } else {
          await vault.clearProfile(profileId);
        }
      } on Object {
        // The Profile-local source tombstone still blocks presentation.
      }
    }
    // Unlike a timeout, explicit owner denial withdraws recognition media.
    if (source.projectionKind == 'personal.me' ||
        source.projectionKind == 'personal.ongoing' ||
        source.projectionKind == 'personal.now') {
      try {
        await ProfileRecognitionImageStore(profileId: profileId).purge();
      } on Object {
        // The revoked projection is already removed from the active reader.
      }
      if (source.projectionKind == 'personal.me') {
        try {
          await ProfilePaths.removePortrait(profileId);
        } on Object {
          // Portrait cleanup is independent of recognition file cleanup.
        }
      }
    }
  }

  /// Inventory is a discoverability observation, not Space authority.
  /// It cannot reintroduce a Workspace whose owner explicitly denied access.
  Future<AcquiredProjection> _withoutRevokedSpaceRows(
    AcquiredProjection acquired,
  ) async {
    final items = acquired.payload['items'];
    if (items is! List) return acquired;
    final rows = await (database.select(
      database.syncSources,
    )..where((row) => row.profileId.equals(profileId))).get();
    final deniedSpaceKeys = <String>{
      for (final row in rows)
        if (row.sourceKey.startsWith('space:') &&
            row.sourceKey.endsWith(':workspace') &&
            row.invalidated &&
            _deniedOwnerState(row.lastErrorCode))
          row.sourceKey.substring(
            'space:'.length,
            row.sourceKey.length - ':workspace'.length,
          ),
    };
    if (deniedSpaceKeys.isEmpty) return acquired;
    final retained = items.where((row) {
      if (row is! Map) return true;
      final id = row['id'];
      return id == null ||
          !deniedSpaceKeys.contains(Uri.encodeComponent(id.toString()));
    }).toList();
    if (retained.length == items.length) return acquired;
    return AcquiredProjection(
      schemaVersion: acquired.schemaVersion,
      payload: {...acquired.payload, 'items': retained},
      sourceGeneratedAt: acquired.sourceGeneratedAt,
      sourceUpdatedAt: acquired.sourceUpdatedAt,
      freshUntil: acquired.freshUntil,
      expiresAt: acquired.expiresAt,
    );
  }

  /// A detail denial only withdraws this Access from cached lists.
  /// Other beneficiary rights remain readable, without inferring authority.
  Future<void> _redactAccessFromCollections(String accessId) async {
    if (accessId.isEmpty) return;
    final pages = await store.readProjections('personal.accesses');
    for (final page in pages) {
      final items = page.payload['items'];
      if (items is! List) continue;
      final retained = items.where((row) {
        if (row is! Map) return true;
        final identity = row['identity'];
        return identity is! Map || identity['id']?.toString() != accessId;
      }).toList();
      if (retained.length == items.length) continue;
      await store.putProjection(
        kind: page.kind,
        resourceKey: page.resourceKey,
        schemaVersion: page.schemaVersion,
        payload: {...page.payload, 'items': retained},
        receivedAt: page.receivedAt,
        sourceGeneratedAt: page.sourceGeneratedAt,
        sourceUpdatedAt: page.sourceUpdatedAt,
        lastVerifiedOnlineAt: page.lastVerifiedOnlineAt,
        freshUntil: page.freshUntil,
        expiresAt: page.expiresAt,
        freshnessPolicyId: page.freshnessPolicyId,
      );
    }
  }

  /// A successful collection cannot resurrect a detail withdrawn by an
  /// explicit owner 403/404. A fresh keyed-detail owner response may later
  /// clear that exact tombstone and restore the resource.
  Future<AcquiredProjection> _withoutRevokedAccessRows(
    AcquiredProjection acquired,
  ) async {
    final items = acquired.payload['items'];
    if (items is! List) return acquired;
    final denied = await (database.select(
      database.syncSources,
    )..where((row) => row.profileId.equals(profileId))).get();
    final deniedIds = <String>{
      for (final row in denied)
        if (row.sourceKey.startsWith('access:') &&
            row.invalidated &&
            _deniedOwnerState(row.lastErrorCode))
          row.sourceKey.substring('access:'.length),
    };
    if (deniedIds.isEmpty) return acquired;
    final retained = items.where((row) {
      if (row is! Map) return true;
      final identity = row['identity'];
      return identity is! Map ||
          !deniedIds.contains(identity['id']?.toString());
    }).toList();
    if (retained.length == items.length) return acquired;
    return AcquiredProjection(
      schemaVersion: acquired.schemaVersion,
      payload: {...acquired.payload, 'items': retained},
      sourceGeneratedAt: acquired.sourceGeneratedAt,
      sourceUpdatedAt: acquired.sourceUpdatedAt,
      freshUntil: acquired.freshUntil,
      expiresAt: acquired.expiresAt,
    );
  }

  /// A collection 403/404 is scoped to the relationship, not every Access.
  /// In particular, a buyer's purchased_for_other list cannot revoke their
  /// independent beneficiary QR presentations.
  Future<void> _withdrawAccessCollectionRelationship(
    SyncSourceDefinition source,
    String code,
  ) async {
    final key = source.resourceKey;
    final relationship = key.split(':').first;
    if (relationship != 'beneficiary' &&
        relationship != 'purchased_for_other') {
      return;
    }
    final pages = await store.readProjections('personal.accesses');
    for (final page in pages) {
      if (page.resourceKey.startsWith('$relationship:')) {
        await store.deleteProjection(page.kind, resourceKey: page.resourceKey);
      }
    }
    final sources = await (database.select(
      database.syncSources,
    )..where((row) => row.profileId.equals(profileId))).get();
    for (final row in sources) {
      if (!row.sourceKey.startsWith('accesses:$relationship:')) continue;
      await (database.update(database.syncSources)..where(
            (item) =>
                item.profileId.equals(profileId) &
                item.sourceKey.equals(row.sourceKey),
          ))
          .write(
            SyncSourcesCompanion(
              invalidated: const Value(true),
              lastErrorCode: Value(code),
            ),
          );
    }
  }

  /// Runs inside the same SQLite transaction as the owner tombstone.
  /// A Workspace denial removes only that Space, including operational
  /// projections. An inventory-level denial withdraws all local Space views.
  Future<void> _withdrawSpaceFacts({
    required String? spaceId,
    required String code,
  }) async {
    final encoded = spaceId == null ? null : Uri.encodeComponent(spaceId);
    final snapshots = await (database.select(
      database.projectionSnapshots,
    )..where((row) => row.profileId.equals(profileId))).get();
    for (final snapshot in snapshots) {
      if (!snapshot.projectionKind.startsWith('space.') ||
          snapshot.projectionKind == 'space.inventory') {
        continue;
      }
      final key = snapshot.resourceKey;
      final inScope =
          spaceId == null ||
          key == encoded ||
          key.startsWith('$encoded|') ||
          key == spaceId ||
          key.startsWith('$spaceId|');
      if (!inScope) continue;
      await store.deleteProjection(snapshot.projectionKind, resourceKey: key);
    }
    final rows = await (database.select(
      database.syncSources,
    )..where((row) => row.profileId.equals(profileId))).get();
    for (final row in rows) {
      final key = row.sourceKey;
      final inScope = spaceId == null
          ? key.startsWith('space:') ||
                key.startsWith('space-day-of:') ||
                key.startsWith('space-live:')
          : key.startsWith('space:$encoded:') ||
                key.startsWith('space-day-of:$spaceId:') ||
                key.startsWith('space-live:$spaceId:');
      if (!inScope) continue;
      await (database.update(database.syncSources)..where(
            (item) =>
                item.profileId.equals(profileId) & item.sourceKey.equals(key),
          ))
          .write(
            SyncSourcesCompanion(
              invalidated: const Value(true),
              lastErrorCode: Value(code),
            ),
          );
    }
    if (spaceId == null) {
      await store.deleteProjection('space.inventory');
      return;
    }
    // Redact only the withdrawn identity. Other Spaces stay discoverable,
    // but the inventory is invalidated for its next owner reconciliation.
    final inventory = await store.readProjection('space.inventory');
    if (inventory == null) return;
    final items = inventory.payload['items'];
    if (items is! List) return;
    final retained = items
        .where((row) => row is! Map || row['id']?.toString() != spaceId)
        .toList();
    if (retained.length == items.length) return;
    await store.putProjection(
      kind: inventory.kind,
      resourceKey: inventory.resourceKey,
      schemaVersion: inventory.schemaVersion,
      payload: {...inventory.payload, 'items': retained},
      receivedAt: inventory.receivedAt,
      sourceGeneratedAt: inventory.sourceGeneratedAt,
      sourceUpdatedAt: inventory.sourceUpdatedAt,
      lastVerifiedOnlineAt: inventory.lastVerifiedOnlineAt,
      freshUntil: inventory.freshUntil,
      expiresAt: inventory.expiresAt,
      freshnessPolicyId: inventory.freshnessPolicyId,
    );
    await (database.update(database.syncSources)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals('space.inventory'),
        ))
        .write(const SyncSourcesCompanion(invalidated: Value(true)));
  }

  Future<void> _recordFailure(SyncSourceDefinition source, String code) {
    return database.transaction(() async {
      await _ensureSource(source);
      final observed =
          await (database.select(database.syncSources)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.sourceKey.equals(source.sourceKey),
              ))
              .getSingleOrNull();
      if (observed?.invalidated == true &&
          _deniedOwnerState(observed?.lastErrorCode)) {
        // A 500 or timeout cannot replace an owner 403/404. The transaction
        // also prevents a concurrent denial from racing this state write.
        return;
      }
      await (database.update(database.syncSources)..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.sourceKey.equals(source.sourceKey),
          ))
          .write(SyncSourcesCompanion(lastErrorCode: Value(code)));
    });
  }

  Future<void> _ensureSource(SyncSourceDefinition source) async {
    await database
        .into(database.syncSources)
        .insert(
          SyncSourcesCompanion.insert(
            profileId: profileId,
            sourceKey: source.sourceKey,
            route: source.path,
          ),
          mode: InsertMode.insertOrIgnore,
        );
  }
}
