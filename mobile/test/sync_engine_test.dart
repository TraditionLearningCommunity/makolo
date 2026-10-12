import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/freshness.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/sync/sync_source.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  test(
    'sync applies owner projections locally and preserves them offline',
    () async {
      var online = true;
      var revision = 1;
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((request) async {
        if (!online) throw const SocketException('offline');
        if (request.url.path == '/api/v1/me/interoperability/') {
          return MockResponse(
            jsonEncode({
              'schema_version': 'z16.v1',
              'context': 'profile',
              'providers': <Object>[],
              'connections': [
                {
                  'id': 'connection-a',
                  'scope': 'profile',
                  'owner': 'intelligence',
                  'provider_protocol': 'openai_compatible',
                  'display_name': 'Personal AI',
                  'available': true,
                  'connected': true,
                  'usable': true,
                  'manageable': true,
                  'enabled': true,
                  'status': 'connected',
                  'health': 'healthy',
                  'capabilities': ['text_generate'],
                  'permissions': {'use': true, 'manage': true},
                },
              ],
              'actions': <Object>[],
              'extensions': <Object>[],
              'webhooks': <Object>[],
              'links': {'self': '/api/v1/me/interoperability/'},
            }),
            200,
          );
        }
        final key = switch (request.url.path) {
          '/api/v1/me/now/' => 'personal.now',
          '/api/v1/me/ongoing/' => 'personal.ongoing',
          '/api/v1/me/' => 'personal.me',
          _ => throw StateError('unexpected route ${request.url.path}'),
        };
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': key,
              'schema_version': 1,
              'generated_at': '2026-09-26T10:00:00Z',
              'scope': 'personal',
            },
            'data': key == 'personal.now'
                ? {
                    'revision': revision,
                    'surface': 'now_me',
                    'freshness': {
                      'state': 'fresh',
                      'observed_at': '2026-09-26T10:00:00Z',
                    },
                    'selection': {'state': 'ready', 'reason': null},
                    'actor_attention_state': 'active',
                    'items': [
                      {
                        'id': 'now:action-1',
                        'human_context': 'Action',
                        'state': 'owner.action_required',
                        'state_meaning': 'Action $revision',
                      },
                    ],
                    'continuation': null,
                    'terminal': {'state': 'ok', 'message': null},
                  }
                : {'revision': revision, 'items': <Object>[]},
          }),
          200,
        );
      });

      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: client.dio,
        tokenStore: tokens,
      );
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final sync = SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'profile-a',
      );

      await sync.refreshRoots();
      expect(
        (await store.readProjection('personal.now'))?.payload['revision'],
        1,
      );
      expect(
        (await store.readProjection(
          'personal.now',
        ))?.payload['actor_attention_state'],
        'active',
      );
      final interoperability = await store.readProjection(
        'personal.interoperability',
      );
      expect(interoperability?.payload['schema_version'], 'z16.v1');
      expect(
        (interoperability?.payload['connections'] as List).single['scope'],
        'profile',
      );

      revision = 2;
      await sync.refreshRoots();
      expect(
        (await store.readProjection('personal.now'))?.payload['revision'],
        2,
      );

      online = false;
      await sync.refreshRoots();
      expect(
        (await store.readProjection('personal.now'))?.payload['revision'],
        2,
      );

      var source = await (database.select(
        database.syncSources,
      )..where((row) => row.sourceKey.equals('personal.now'))).getSingle();
      expect(source.invalidated, isFalse);
      expect(source.lastErrorCode, isNotNull);

      online = true;
      revision = 3;
      await sync.refreshRoots();
      expect(
        (await store.readProjection('personal.now'))?.payload['revision'],
        3,
      );
      source = await (database.select(
        database.syncSources,
      )..where((row) => row.sourceKey.equals('personal.now'))).getSingle();
      expect(source.lastErrorCode, isNull);
    },
  );

  test(
    'keyed acquisition parses and applies through a source definition',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((request) async {
        expect(request.url.path, '/api/v1/activities/activity-42/');
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': 'activity.detail',
              'schema_version': 1,
              'generated_at': '2026-09-30T06:00:00Z',
            },
            'data': {'id': 'activity-42', 'title': 'Formation'},
          }),
          200,
        );
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final sync = SyncEngine(
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final source = SyncSourceDefinition.projectionEnvelope(
        sourceKey: 'activity:activity-42',
        owner: 'Activity',
        path: 'api/v1/activities/activity-42/',
        projectionKind: 'activity.detail',
        resourceKey: 'activity-42',
        category: SyncSourceCategory.keyedDetail,
        freshnessPolicy: const FreshnessPolicy(id: 'contextual'),
      );

      await sync.pullSource(source);

      final projection = await store.readProjection(
        'activity.detail',
        resourceKey: 'activity-42',
      );
      expect(projection?.payload['title'], 'Formation');
      expect(projection?.freshnessPolicyId, 'contextual');
      final persistedSource = await (database.select(
        database.syncSources,
      )..where((row) => row.sourceKey.equals(source.sourceKey))).getSingle();
      expect(persistedSource.route, source.path);
      expect(persistedSource.invalidated, isFalse);
    },
  );

  test(
    '403/404 removes only the source-scoped snapshot, not resource identity',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((_) async {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'not_found', 'message': 'Gone from this scope'},
          }),
          404,
        );
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      await store.putProjection(
        kind: 'activity.detail',
        resourceKey: 'activity-42',
        schemaVersion: 1,
        payload: {'id': 'activity-42'},
      );
      await database
          .into(database.resourceIndex)
          .insert(
            ResourceIndexCompanion.insert(
              profileId: 'profile-a',
              resourceKind: 'Activity',
              resourceId: 'activity-42',
              projectionKind: 'activity.detail',
              updatedAt: DateTime.utc(2026, 9, 30),
            ),
          );

      final sync = SyncEngine(
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final source = SyncSourceDefinition.projectionEnvelope(
        sourceKey: 'activity:activity-42',
        owner: 'Activity',
        path: 'api/v1/activities/activity-42/',
        projectionKind: 'activity.detail',
        resourceKey: 'activity-42',
        category: SyncSourceCategory.keyedDetail,
      );

      await expectLater(sync.pullSource(source), throwsA(isA<Exception>()));

      expect(
        await store.readProjection(
          'activity.detail',
          resourceKey: 'activity-42',
        ),
        isNull,
      );
      expect(await database.select(database.resourceIndex).get(), hasLength(1));
      final persistedSource = await (database.select(
        database.syncSources,
      )..where((row) => row.sourceKey.equals(source.sourceKey))).getSingle();
      expect(persistedSource.invalidated, isTrue);
      expect(persistedSource.lastErrorCode, 'not_found');
    },
  );
}
