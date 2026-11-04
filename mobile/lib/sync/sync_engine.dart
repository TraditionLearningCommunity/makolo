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

class _SyncCoordinator {
  final Map<String, int> generations = {};
  final Map<String, int> discoveryEpochs = {};
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

  // Shared among SyncEngine instances bound to one SQLite connection.
  // Separate runtimes cannot resurrect a previously withdrawn Profile fact.
  _SyncCoordinator get _coordinator =>
      _coordinators[database] ??= _SyncCoordinator();
  String _scopeKey(String sourceKey) => '$profileId|$sourceKey';
  int get _discoveryRevocationEpoch =>
      _coordinator.discoveryEpochs[profileId] ?? 0;
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
    for (final root in roots) {
      await pull(root);
    }
    await pullInteroperability();
  }

  Future<bool> refreshRoots() async {
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

  Future<void> pullSource(SyncSourceDefinition source) async {
    if (!_active) return;
    final key = _scopeKey(source.sourceKey);
    final coordinator = _coordinator;
    final generation = (coordinator.generations[key] ?? 0) + 1;
    coordinator.generations[key] = generation;
    final epoch = _discoveryRevocationEpoch;
    bool isCurrent() =>
        _active &&
        coordinator.generations[key] == generation &&
        (!_isDiscoveryRelated(source) || _discoveryRevocationEpoch == epoch);
    try {
      final response = await api.get(source.path);
      if (!isCurrent()) return;
      final acquired = source.parser(response);
      if (!isCurrent()) return;
      // The owner sometimes exposes a Profile actor. If present, its
      // identity must match the authenticated local storage boundary.
      if (source.actorScope.isPersonal && source.owner == 'Profile') {
        final actor = acquired.payload['actor'];
        if (actor is Map && actor['id'] != null &&
            actor['id'].toString() != profileId) {
          throw const FormatException('Owner Profile mismatch');
        }
      }

      await database.transaction(() async {
        // Across engine instances and process-resumed requests, a response
        // with an older owner generation cannot replace newer local facts.
        final observed = await (database.select(database.syncSources)
              ..where((row) =>
                  row.profileId.equals(profileId) &
                  row.sourceKey.equals(source.sourceKey)))
            .getSingleOrNull();
        if (acquired.sourceGeneratedAt != null &&
            observed?.generatedAtSeen != null &&
            acquired.sourceGeneratedAt!.isBefore(observed!.generatedAtSeen!)) {
          return;
        }
        if (!isCurrent()) return;
        await source.applier(
          SyncApplyContext(
            database: database,
            store: store,
            profileId: profileId,
            source: source,
          ),
          acquired,
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
    } on TimeoutException {
      if (isCurrent()) await _recordFailure(source, 'timeout');
      rethrow;
    } on MakoloApiError catch (error) {
      if (isCurrent()) {
        if (error.statusCode == 403 || error.statusCode == 404) {
          // Arbitrary owner error codes are not stable tombstone names.
          // Normalize HTTP authority refusal so every local reader can
          // recognize it even after a cold start.
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
    final key = _scopeKey(source.sourceKey);
    final coordinator = _coordinator;
    coordinator.generations[key] = (coordinator.generations[key] ?? 0) + 1;
    await _ensureSource(source);
    await (database.update(database.syncSources)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals(source.sourceKey),
        ))
        .write(const SyncSourcesCompanion(invalidated: Value(true)));
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

  Future<void> _recordScopedUnavailable(
    SyncSourceDefinition source,
    String code,
  ) async {
    // Invalidate all concurrently in-flight Discovery readers. A successful
    // response to another request, started before this denial, cannot
    // rehydrate a derived collection after the withdrawal committed.
    final coordinator = _coordinator;
    final key = _scopeKey(source.sourceKey);
    coordinator.generations[key] = (coordinator.generations[key] ?? 0) + 1;
    if (_isDiscoveryRelated(source)) {
      coordinator.discoveryEpochs[profileId] = _discoveryRevocationEpoch + 1;
    }
    // A denied History owner invalidates its previously received search
    // views as a family. Older in-flight pages cannot restore them.
    if (source.owner == 'ProfileHistory') {
      for (final key in coordinator.generations.keys
          .where((key) => key.startsWith('$profileId|history:')).toList()) {
        coordinator.generations[key] =
            (coordinator.generations[key] ?? 0) + 1;
      }
    }
    await database.transaction(() async {
      await store.deleteProjection(
        source.projectionKind,
        resourceKey: source.resourceKey,
      );
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
            .write(SyncSourcesCompanion(
              invalidated: const Value(true),
              lastErrorCode: Value(code),
            ));
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
        source.projectionKind == 'personal.accesses') {
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

  Future<void> _recordFailure(SyncSourceDefinition source, String code) async {
    await _ensureSource(source);
    await (database.update(database.syncSources)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals(source.sourceKey),
        ))
        .write(SyncSourcesCompanion(lastErrorCode: Value(code)));
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
