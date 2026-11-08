import 'dart:convert';

import 'package:drift/drift.dart' show Value;

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/sync/sync_source.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  test(
    'organizer 404 means endpoint unavailable, not revoked collection',
    () async {
      var deployed = false;
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      const projection = 'objective.organizer.collection';
      const resourceKey = 'offset:0:limit:50';
      const sourceKey = 'objective.organizer.collection:0:50';
      await store.putProjection(
        kind: projection,
        resourceKey: resourceKey,
        schemaVersion: 1,
        payload: {
          'actor': {'type': 'profile', 'id': 'profile-a'},
          'items': [
            {'kind': 'project', 'id': 'project-a', 'title': 'Projet connu'},
          ],
          'page': {
            'offset': 0,
            'limit': 50,
            'next_offset': 50,
            'has_more': false,
          },
        },
      );

      final client = MockClient((_) async {
        if (!deployed) {
          return MockResponse(
            jsonEncode({
              'error': {'code': 'not_found', 'message': 'Route not deployed'},
            }),
            404,
          );
        }
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': projection,
              'schema_version': 1,
              'scope': 'authorized',
              'generated_at': '2026-11-08T12:00:00Z',
            },
            'data': {
              'actor': {'type': 'profile', 'id': 'profile-a'},
              'items': [],
              'page': {
                'offset': 0,
                'limit': 50,
                'next_offset': 50,
                'has_more': false,
              },
            },
          }),
          200,
        );
      });
      final engine = SyncEngine(
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: MemoryTokenStore(
            session: const AuthSession(
              accessToken: 'access',
              refreshToken: 'refresh',
              profileId: 'profile-a',
            ),
          ),
        ),
        store: store,
        database: db,
        profileId: 'profile-a',
      );
      final source = SyncSourceDefinition.projectionEnvelope(
        sourceKey: sourceKey,
        owner: 'Objectives',
        path: 'api/v1/objectives/organizer/?limit=50&offset=0',
        projectionKind: projection,
        resourceKey: resourceKey,
        category: SyncSourceCategory.collection,
      );

      // A missing route is not authority withdrawal.
      await expectLater(engine.pullSource(source), throwsA(isA<Exception>()));
      expect(
        await store.readProjection(projection, resourceKey: resourceKey),
        isNotNull,
      );
      var status = await (db.select(db.syncSources)).getSingle();
      expect(status.invalidated, isFalse);
      expect(status.lastErrorCode, 'endpoint_unavailable');

      // Some previously installed clients had persisted the same HTTP 404 as
      // a permanent owner tombstone. Migrate only this known false-revocation.
      await (db.update(
        db.syncSources,
      )..where((row) => row.sourceKey.equals(sourceKey))).write(
        const SyncSourcesCompanion(
          invalidated: Value(true),
          lastErrorCode: Value('not_found'),
        ),
      );
      await expectLater(engine.pullSource(source), throwsA(isA<Exception>()));
      status = await (db.select(db.syncSources)).getSingle();
      expect(status.invalidated, isFalse);
      expect(status.lastErrorCode, 'endpoint_unavailable');
      expect(
        await store.readProjection(projection, resourceKey: resourceKey),
        isNotNull,
      );

      deployed = true;
      await engine.pullSource(source);
      status = await (db.select(db.syncSources)).getSingle();
      expect(status.invalidated, isFalse);
      expect(status.lastErrorCode, isNull);
      final received = await store.readProjection(
        projection,
        resourceKey: resourceKey,
      );
      expect(received?.payload['items'], isEmpty);
    },
  );
}
