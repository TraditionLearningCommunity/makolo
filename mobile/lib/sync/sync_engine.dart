import 'dart:async';

import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../data/files/profile_recognition_image_store.dart';
import '../data/files/profile_paths.dart';
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

class SyncEngine {
  SyncEngine({
    required this.api,
    required this.store,
    required this.database,
    required this.profileId,
  });

  final MakoloApiClient api;
  final ProfileStore store;
  final MakoloDatabase database;
  final String profileId;

  // Only the most recently started request for a source may change its local
  // state. A late 200 must not undo a newer owner 403/404 revocation.
  final Map<String, int> _sourceGenerations = {};

  static const _discoveryDerivedKinds = <String>[
    'discovery.items',
    'discovery.map',
    'discovery.presented-window',
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
    final key = source.sourceKey;
    final generation = (_sourceGenerations[key] ?? 0) + 1;
    _sourceGenerations[key] = generation;
    bool isCurrent() => _sourceGenerations[key] == generation;
    try {
      final response = await api.get(source.path);
      if (!isCurrent()) return;
      final acquired = source.parser(response);
      if (!isCurrent()) return;

      await database.transaction(() async {
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
              Uri.parse(source.path).queryParameters.containsKey('continuation');
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
    await _ensureSource(source);
    await (database.update(database.syncSources)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals(source.sourceKey),
        ))
        .write(const SyncSourcesCompanion(invalidated: Value(true)));
  }

  Future<void> _recordScopedUnavailable(
    SyncSourceDefinition source,
    String code,
  ) async {
    await database.transaction(() async {
      await store.deleteProjection(
        source.projectionKind,
        resourceKey: source.resourceKey,
      );
      // The field, map, N2 and previews are a composition of owner facts.
      // Once any such owner explicitly refuses access, retaining a copy
      // elsewhere is a privacy leak. Transport errors never enter this path.
      if (source.owner == 'Discovery' ||
          source.projectionKind == 'activity.detail' ||
          source.projectionKind == 'occurrence.detail') {
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
                  row.sourceKey.like('discovery:%'),
            ))
            .write(const SyncSourcesCompanion(invalidated: Value(true)));
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
    if (source.owner == 'Discovery' ||
        source.projectionKind == 'activity.detail' ||
        source.projectionKind == 'occurrence.detail') {
      try {
        await const DiscoveryOfflineStore().purgeAutomaticRecognition();
      } on Object {
        // Projection withdrawal has already committed in SQLite.
      }
    }
    // A root owner denial revokes its derived continuation too. A network
    // failure never reaches this branch and therefore preserves it.
    if (source.projectionKind == 'personal.now') {
      await store.deleteProjection('personal.now.continuation');
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
