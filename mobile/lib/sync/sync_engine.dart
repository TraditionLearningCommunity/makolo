import 'dart:async';

import 'package:drift/drift.dart';

import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../network/api_error.dart';
import '../network/makolo_api_client.dart';
import 'projection_contract.dart';

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

  Future<void> bootstrap() async {
    for (final root in roots) {
      await pull(root);
    }
  }

  Future<void> refreshRoots() async {
    for (final root in roots) {
      try {
        await pull(root);
      } on TimeoutException {
        await _recordFailure(root, 'timeout');
      } on MakoloApiError catch (error) {
        await _recordFailure(root, error.code);
        if (error.statusCode == 401) rethrow;
      } on Object {
        await _recordFailure(root, 'transport_error');
      }
    }
  }

  Future<void> pull(SyncRoot root) async {
    final response = await api.get(root.path);
    final envelope = ProjectionEnvelope.parse(response.jsonObject());
    if (envelope.projection != root.key) {
      throw FormatException(
        'Expected ${root.key}, got ${envelope.projection}',
      );
    }

    await database.transaction(() async {
      await store.putProjection(
        kind: root.key,
        schemaVersion: envelope.schemaVersion,
        payload: envelope.data,
        sourceGeneratedAt: envelope.generatedAt,
      );
      await database.into(database.syncSources).insertOnConflictUpdate(
            SyncSourcesCompanion.insert(
              profileId: profileId,
              sourceKey: root.key,
              route: root.path,
              schemaVersionSeen: Value(envelope.schemaVersion),
              lastSuccessAt: Value(DateTime.now().toUtc()),
              generatedAtSeen: Value(envelope.generatedAt),
              invalidated: const Value(false),
            ),
          );
    });
  }

  Future<void> _recordFailure(SyncRoot root, String code) {
    return database.into(database.syncSources).insertOnConflictUpdate(
          SyncSourcesCompanion.insert(
            profileId: profileId,
            sourceKey: root.key,
            route: root.path,
            invalidated: const Value(true),
            lastErrorCode: Value(code),
          ),
        );
  }
}
