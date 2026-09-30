import 'dart:async';

import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../network/api_error.dart';
import '../network/makolo_api_client.dart';
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

  Future<void> refreshRoots() async {
    for (final root in roots) {
      await refreshSource(_rootSource(root));
    }
    await refreshSource(_interoperabilitySource);
  }

  Future<void> refreshSource(SyncSourceDefinition source) async {
    try {
      await pullSource(source);
    } on MakoloApiError catch (error) {
      if (error.statusCode == 401) rethrow;
    } on Object {
      // The failure is recorded by pullSource. Existing local data is kept.
    }
  }

  Future<void> pull(SyncRoot root) => pullSource(_rootSource(root));

  Future<void> pullInteroperability() => pullSource(_interoperabilitySource);

  Future<void> pullSource(SyncSourceDefinition source) async {
    try {
      final response = await api.get(source.path);
      final acquired = source.parser(response);

      await database.transaction(() async {
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
      await _recordFailure(source, 'timeout');
      rethrow;
    } on MakoloApiError catch (error) {
      if (error.statusCode == 403 || error.statusCode == 404) {
        await _recordScopedUnavailable(source, error.code);
      } else {
        await _recordFailure(source, error.code);
      }
      rethrow;
    } on MakoloTransportError catch (error) {
      await _recordFailure(source, error.code);
      rethrow;
    } on Object {
      await _recordFailure(source, 'transport_error');
      rethrow;
    }
  }

  Future<void> invalidate(SyncSourceDefinition source) async {
    await _ensureSource(source);
    await (database.update(database.syncSources)
          ..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.sourceKey.equals(source.sourceKey),
          ))
        .write(const SyncSourcesCompanion(invalidated: Value(true)));
  }

  Future<void> _recordScopedUnavailable(
    SyncSourceDefinition source,
    String code,
  ) {
    return database.transaction(() async {
      await store.deleteProjection(
        source.projectionKind,
        resourceKey: source.resourceKey,
      );
      await _ensureSource(source);
      await (database.update(database.syncSources)
            ..where(
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
  }

  Future<void> _recordFailure(
    SyncSourceDefinition source,
    String code,
  ) async {
    await _ensureSource(source);
    await (database.update(database.syncSources)
          ..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.sourceKey.equals(source.sourceKey),
          ))
        .write(SyncSourcesCompanion(lastErrorCode: Value(code)));
  }

  Future<void> _ensureSource(SyncSourceDefinition source) {
    return database
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
