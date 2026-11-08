import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart' show Value;
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
    'simultaneous owner reads share one request and preserve local facts',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final gate = Completer<void>();
      final entered = Completer<void>();
      var requests = 0;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
        dio: MockClient((request) async {
          requests++;
          if (!entered.isCompleted) entered.complete();
          await gate.future;
          return MockResponse(
            jsonEncode({
              'meta': {
                'projection': 'personal.me',
                'schema_version': 1,
                'scope': 'personal',
                'generated_at': '2026-11-08T08:00:00Z',
              },
              'data': {
                'actor': {'type': 'profile', 'id': 'profile-a'},
                'name': 'Owner result',
              },
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        store: store,
        database: db,
        profileId: 'profile-a',
      );
      final first = sync.refreshPersonalMe();
      await entered.future;
      final second = sync.refreshPersonalMe();
      expect(requests, 1);
      gate.complete();
      expect(await first, isTrue);
      expect(await second, isTrue);
      expect(
        (await store.readProjection('personal.me'))?.payload['name'],
        'Owner result',
      );
    },
  );

  test(
    'invalidating an in-flight owner read permits a fresh request',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final releaseOld = Completer<void>();
      final firstStarted = Completer<void>();
      var requests = 0;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
        dio: MockClient((request) async {
          final number = ++requests;
          if (number == 1) {
            firstStarted.complete();
            await releaseOld.future;
          }
          return MockResponse(
            jsonEncode({
              'meta': {
                'projection': 'personal.me',
                'schema_version': 1,
                'scope': 'personal',
                'generated_at': number == 1
                    ? '2026-11-08T08:00:00Z'
                    : '2026-11-08T08:01:00Z',
              },
              'data': {
                'actor': {'type': 'profile', 'id': 'profile-a'},
                'name': number == 1 ? 'Obsolete' : 'Current',
              },
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        store: store,
        database: db,
        profileId: 'profile-a',
      );
      final previous = sync.refreshPersonalMe();
      await firstStarted.future;
      await sync.invalidate(
        SyncSourceDefinition.projectionEnvelope(
          sourceKey: 'personal.me',
          owner: 'Profile',
          path: 'api/v1/me/',
          projectionKind: 'personal.me',
        ),
      );
      expect(await sync.refreshPersonalMe(), isTrue);
      releaseOld.complete();
      expect(await previous, isTrue);
      expect(requests, 2);
      expect(
        (await store.readProjection('personal.me'))?.payload['name'],
        'Current',
      );
    },
  );

  test(
    'composed Me edits reuse the single canonical root reconciliation',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      await store.putProjection(
        kind: 'personal.me',
        schemaVersion: 1,
        payload: const {
          'actor': {'id': 'profile-a'},
          'name': 'Local',
        },
      );
      final requests = <String>[];
      var offline = false;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
        dio: MockClient((request) async {
          requests.add(request.url.path);
          if (offline) {
            return const MockResponse('{"detail":"offline"}', 503);
          }
          return MockResponse(
            jsonEncode({
              'meta': {
                'projection': 'personal.me',
                'schema_version': 1,
                'scope': 'personal',
                'generated_at': '2026-11-05T12:00:00Z',
              },
              'data': {
                'actor': {'type': 'profile', 'id': 'profile-a'},
                'name': 'Confirmed',
              },
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        database: db,
        store: store,
        profileId: 'profile-a',
      );
      expect(await sync.refreshPersonalMe(), isTrue);
      expect(requests, ['/api/v1/me/']);
      expect(
        (await store.readProjection('personal.me'))?.payload['name'],
        'Confirmed',
      );

      offline = true;
      expect(await sync.refreshPersonalMe(), isFalse);
      expect(
        (await store.readProjection('personal.me'))?.payload['name'],
        'Confirmed',
        reason: 'Transport failure never clears earlier owner knowledge',
      );
    },
  );

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

      expect(await sync.refreshRoots(), isTrue);
      expect(
        (await store.readProjection('personal.now'))?.payload['revision'],
        1,
      );
      expect(
        (await store.readProjection('personal.now'))
            ?.payload['actor_attention_state'],
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
      expect(await sync.refreshRoots(), isTrue);
      expect(
        (await store.readProjection('personal.now'))?.payload['revision'],
        2,
      );

      online = false;
      // A failed refresh must not erase previously acquired owner facts.
      expect(await sync.refreshRoots(), isFalse);
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
      expect(await sync.refreshRoots(), isTrue);
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

  test('slow Now does not hold back Ongoing and Me on first sync', () async {
    final nowReply = Completer<MockResponse>();
    final otherRootsSeen = Completer<void>();
    final seen = <String>{};
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      final path = request.url.path;
      if (path == '/api/v1/me/now/') return nowReply.future;
      if (path == '/api/v1/me/interoperability/') {
        return MockResponse(
          jsonEncode({
            'schema_version': 'z16.v1',
            'context': 'profile',
            'providers': <Object>[],
            'connections': <Object>[],
            'actions': <Object>[],
            'extensions': <Object>[],
            'webhooks': <Object>[],
          }),
          200,
        );
      }
      final key = switch (path) {
        '/api/v1/me/ongoing/' => 'personal.ongoing',
        '/api/v1/me/' => 'personal.me',
        _ => throw StateError('Unexpected root: $path'),
      };
      seen.add(key);
      if (seen.length == 2 && !otherRootsSeen.isCompleted) {
        otherRootsSeen.complete();
      }
      return MockResponse(
        jsonEncode({
          'meta': {
            'projection': key,
            'schema_version': 1,
            'generated_at': '2026-10-30T09:00:00Z',
            'scope': 'personal',
          },
          'data': {'items': <Object>[]},
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

    final refresh = sync.refreshRoots();
    try {
      await otherRootsSeen.future.timeout(const Duration(seconds: 2));
      // The Now request remains unresolved: the other independent roots
      // must have been requested regardless of the server's response order.
      expect(nowReply.isCompleted, isFalse);
      expect(seen, containsAll(['personal.ongoing', 'personal.me']));
    } finally {
      if (!nowReply.isCompleted) {
        nowReply.complete(
          MockResponse(
            jsonEncode({
              'meta': {
                'projection': 'personal.now',
                'schema_version': 1,
                'generated_at': '2026-10-30T09:00:00Z',
                'scope': 'personal',
              },
              'data': {'items': <Object>[]},
            }),
            200,
          ),
        );
      }
      await refresh;
    }
    expect(await store.readProjection('personal.ongoing'), isNotNull);
    expect(await store.readProjection('personal.me'), isNotNull);
  });

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
        indexedResourceKind: 'Activity',
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
      expect(
        (await store.readKnownResources(search: 'formation')).single.id,
        'activity-42',
      );
      final persistedSource = await (database.select(
        database.syncSources,
      )..where((row) => row.sourceKey.equals(source.sourceKey))).getSingle();
      expect(persistedSource.route, source.path);
      expect(persistedSource.invalidated, isFalse);
    },
  );

  test('keyed index rejects an owner identity mismatch atomically', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient(
      (_) async => MockResponse(
        jsonEncode({
          'meta': {'projection': 'activity.detail', 'schema_version': 1},
          'data': {'id': 'another-activity', 'title': 'Unrelated'},
        }),
        200,
      ),
    );
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
      sourceKey: 'activity:requested',
      owner: 'Activities',
      path: 'api/v1/activities/requested/',
      projectionKind: 'activity.detail',
      resourceKey: 'requested',
      indexedResourceKind: 'Activity',
      category: SyncSourceCategory.keyedDetail,
    );

    await expectLater(sync.pullSource(source), throwsFormatException);
    expect(
      await store.readProjection('activity.detail', resourceKey: 'requested'),
      isNull,
    );
    expect(await store.readKnownResources(), isEmpty);
  });

  test(
    'future local clock observation cannot indefinitely freeze acquisition',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      await store.putProjection(
        kind: 'test.known',
        schemaVersion: 1,
        payload: {'id': 'local-old'},
      );
      final source = SyncSourceDefinition.projectionEnvelope(
        sourceKey: 'test.known',
        owner: 'Test',
        path: 'api/v1/test/known/',
        projectionKind: 'test.known',
      );
      await database
          .into(database.syncSources)
          .insert(
            SyncSourcesCompanion.insert(
              profileId: 'profile-a',
              sourceKey: source.sourceKey,
              route: source.path,
              lastSuccessAt: Value(
                DateTime.now().toUtc().add(const Duration(days: 3)),
              ),
            ),
          );
      var requests = 0;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
        dio: MockClient((_) async {
          requests++;
          return MockResponse(
            jsonEncode({
              'meta': {'projection': 'test.known', 'schema_version': 1},
              'data': {'id': 'owner-fresh'},
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      sync.registerPreparedSource(source);
      expect(await sync.refreshPreparedSources(), isTrue);
      expect(requests, 1);
      expect(
        (await store.readProjection('test.known'))?.payload['id'],
        'owner-fresh',
      );
    },
  );

  test('prepared owner pages acquire progressively without a screen', () async {
    var calls = 0;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      calls++;
      final page = int.parse(
        request.url.pathSegments.lastWhere((segment) => segment.isNotEmpty),
      );
      final amount = page == 3 ? 40 : 10;
      return MockResponse(
        jsonEncode({
          'meta': {
            'projection': 'test.collection',
            'schema_version': 1,
            'generated_at': '2026-11-05T06:00:00Z',
          },
          'data': {
            'results': List.generate(
              amount,
              (index) => {'id': 'item-$page-$index'},
            ),
          },
        }),
        200,
      );
    });
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final other = ProfileStore(database, 'profile-b');
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
    for (var page = 1; page <= 3; page++) {
      sync.registerPreparedSource(
        SyncSourceDefinition.projectionEnvelope(
          sourceKey: 'test:page:$page',
          owner: 'Test',
          path: 'api/v1/test/$page/',
          projectionKind: 'test.collection',
          resourceKey: 'page:$page',
          category: SyncSourceCategory.collection,
        ),
      );
    }

    expect(await sync.refreshPreparedSources(maxRequests: 1), isTrue);
    expect(calls, 1);
    expect(await store.readProjections('test.collection'), hasLength(1));
    expect(await sync.refreshPreparedSources(maxRequests: 1), isTrue);
    expect(calls, 2);
    expect(await sync.refreshPreparedSources(maxRequests: 1), isTrue);
    expect(calls, 3);
    final pages = await store.readProjections('test.collection');
    expect(pages, hasLength(3));
    expect(
      pages.fold<int>(
        0,
        (total, projection) =>
            total + (projection.payload['results'] as List).length,
      ),
      60,
    );
    expect(await other.readProjections('test.collection'), isEmpty);

    expect(await sync.refreshPreparedSources(maxRequests: 1), isTrue);
    expect(calls, 3, reason: 'Fresh owner sources are not fetched each cycle');
  });

  test('prepared delegated owner refresh observes persisted failure', () async {
    var online = true;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((_) async {
      if (!online) {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'owner_unavailable', 'message': 'Unavailable'},
          }),
          503,
        );
      }
      return MockResponse(
        jsonEncode({
          'meta': {'projection': 'test.collection', 'schema_version': 1},
          'data': {'results': <Object>[]},
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
      sourceKey: 'delegated',
      owner: 'Test',
      path: 'api/v1/test/',
      projectionKind: 'test.collection',
    );
    // refreshSource is deliberately a best-effort repository entrypoint.
    sync.registerPreparedSource(
      source,
      acquire: () => sync.refreshSource(source),
    );
    expect(await sync.refreshPreparedSources(), isTrue);
    expect(await store.readProjection('test.collection'), isNotNull);

    online = false;
    await sync.invalidate(source);
    expect(await sync.refreshPreparedSources(), isFalse);
    expect(
      await store.readProjection('test.collection'),
      isNotNull,
      reason: 'A server failure cannot erase owner facts acquired earlier.',
    );
  });

  test('owner denial stays withdrawn until explicit revalidation', () async {
    var calls = 0;
    var allowed = false;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      calls++;
      if (!allowed) {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied', 'message': 'Denied'},
          }),
          403,
        );
      }
      return MockResponse(
        jsonEncode({
          'meta': {
            'projection': 'test.collection',
            'schema_version': 1,
            'generated_at': '2026-11-05T07:00:00Z',
          },
          'data': {'results': <Object>[]},
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
      sourceKey: 'test:owner',
      owner: 'Test',
      path: 'api/v1/test/',
      projectionKind: 'test.collection',
    );
    sync.registerPreparedSource(source);

    expect(await sync.refreshPreparedSources(), isTrue);
    expect(calls, 1);
    expect(await store.readProjection('test.collection'), isNull);
    expect(await sync.refreshPreparedSources(), isTrue);
    expect(calls, 1, reason: 'A confirmed denial is not a retry timer');

    allowed = true;
    await sync.invalidate(source);
    expect(await sync.refreshPreparedSources(), isTrue);
    expect(calls, 2);
    expect(await store.readProjection('test.collection'), isNotNull);
  });

  test('prepared registration rejects signed continuation replay', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final sync = SyncEngine(
      api: MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: MockClient((_) async => MockResponse('{}', 200)).dio,
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
      ),
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    expect(
      () => sync.registerPreparedSource(
        SyncSourceDefinition.projectionEnvelope(
          sourceKey: 'cursor',
          owner: 'Discovery',
          path: 'api/v1/discovery/items/?continuation=signed',
          projectionKind: 'discovery.items',
        ),
      ),
      throwsArgumentError,
    );
  });

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
