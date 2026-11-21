import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/notifications/notification_repository.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  late MakoloDatabase database;
  late ProfileStore store;

  setUp(() {
    database = MakoloDatabase.memory();
    store = ProfileStore(database, 'profile-a');
  });

  tearDown(() async {
    await database.close();
  });

  NotificationRepository repositoryFor(
    Future<MockResponse> Function(MockRequest request) handler,
  ) {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient(handler).dio,
    );
    final sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    return NotificationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
  }

  test(
    'notification list stays owner-backed and mark read reprojections',
    () async {
      var read = false;
      final requests = <String>[];
      final repository = repositoryFor((request) async {
        requests.add(request.url.path);
        if (request.url.path == '/api/v1/notifications/notification-1/read/') {
          read = true;
          return MockResponse(
            jsonEncode({
              'id': 'notification-1',
              'title': 'Document accepté',
              'message': 'Votre document a été accepté.',
              'is_read': true,
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/notifications/') {
          return MockResponse(
            jsonEncode({
              'count': 1,
              'next': null,
              'previous': null,
              'results': [
                {
                  'id': 'notification-1',
                  'kind': 'system',
                  'category': 'system',
                  'title': 'Document accepté',
                  'message': 'Votre document a été accepté.',
                  'navigation': {
                    'schema_version': 1,
                    'target': 'journey',
                    'resource': {'kind': 'journey', 'id': 'journey-1'},
                    'links': {'api': '/api/v1/me/journeys/journey-1/'},
                  },
                  'is_read': read,
                  'read_at': read ? '2026-10-09T09:00:00Z' : null,
                  'created_at': '2026-10-09T08:30:00Z',
                },
              ],
            }),
            200,
          );
        }
        throw StateError('Unexpected request ${request.url.path}');
      });

      await repository.refreshList();
      var stored = await repository.readList();
      expect((stored?.payload['results'] as List).single['is_read'], false);

      await repository.markRead('notification-1');
      stored = await repository.readList();
      expect((stored?.payload['results'] as List).single['is_read'], true);
      expect(requests, contains('/api/v1/notifications/notification-1/read/'));
    },
  );

  test('preferences remain local until a remote patch is confirmed', () async {
    var push = true;
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/accounts/notification-preferences/' &&
          request.data != null) {
        final body = request.data as Map;
        push = body['push_notifications'] as bool;
      }
      if (request.url.path == '/api/v1/accounts/notification-preferences/') {
        return MockResponse(
          jsonEncode({
            'push_notifications': push,
            'email_notifications': true,
            'security_notifications': true,
            'event_notifications': true,
            'service_notifications': true,
            'opportunity_notifications': true,
            'marketing_notifications': false,
            'quiet_hours_enabled': false,
            'quiet_hours_start': null,
            'quiet_hours_end': null,
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url.path}');
    });

    await repository.refreshPreferences();
    await repository.updatePreferences({'push_notifications': false});

    final stored = await repository.readPreferences();
    expect(stored?.payload['push_notifications'], false);
  });
  test(
    'continuation loads all rows once and read keeps the loaded window',
    () async {
      final requests = <String>[];
      var marked = false;
      List<Map<String, Object?>> batch(int start) => List.generate(15, (index) {
        final id = 'notification-${start + index}';
        return <String, Object?>{
          'id': id,
          'title': 'Information ${start + index}',
          'message': 'Contenu.',
          'is_read': false,
          'created_at': '2026-11-04T07:00:00Z',
        };
      });
      final repository = repositoryFor((request) async {
        requests.add(request.url.toString());
        if (request.url.path == '/api/v1/notifications/notification-0/read/') {
          marked = true;
          return MockResponse('{"is_read":true}', 200);
        }
        if (request.url.path != '/api/v1/notifications/') {
          throw StateError('Unexpected ${request.url}');
        }
        final cursor = request.url.queryParameters['cursor'];
        return MockResponse(
          jsonEncode({
            'count': 30,
            'total_count': 30,
            'unread_count': marked ? 29 : 30,
            'next': cursor == null
                ? 'https://makolo.invalid/api/v1/notifications/?cursor=second'
                : null,
            'previous': null,
            'results': batch(cursor == null ? 0 : 15),
          }),
          200,
        );
      });

      await repository.refreshList();
      expect((await repository.readList())!.payload['results'], hasLength(15));
      expect(await repository.loadMore(), true);
      var stored = (await repository.readList())!.payload;
      expect(stored['results'], hasLength(30));
      expect(stored['next'], isNull);
      expect(await repository.loadMore(), false);

      await repository.markRead('notification-0');
      stored = (await repository.readList())!.payload;
      expect(stored['results'], hasLength(30));
      expect(stored['unread_count'], 29);
      expect((stored['results'] as List).first['is_read'], true);
      expect(
        requests.where((path) => path.contains('cursor=second')),
        hasLength(1),
      );
    },
  );

  test(
    'unread filter uses server scope and continues beyond the first 15',
    () async {
      final requests = <Uri>[];
      final repository = repositoryFor((request) async {
        requests.add(request.url);
        if (request.url.path.endsWith('/unread-0/read/')) {
          return const MockResponse('{"is_read":true}', 200);
        }
        if (request.url.path.endsWith('/read-all/')) {
          return const MockResponse('{"updated":29}', 200);
        }
        final unread = request.url.queryParameters['filter'] == 'unread';
        final second = request.url.queryParameters.containsKey('cursor');
        return MockResponse(
          jsonEncode({
            'count': unread ? 30 : 89,
            'total_count': 89,
            'unread_count': 30,
            'next': unread && !second
                ? 'https://makolo.invalid/api/v1/notifications/?cursor=second&filter=unread'
                : null,
            'results': List.generate(
              unread ? 15 : 1,
              (i) => {
                'id': unread ? 'unread-${i + (second ? 15 : 0)}' : 'read-0',
                'is_read': !unread,
              },
            ),
          }),
          200,
        );
      });
      await repository.refreshList();
      await repository.refreshList(onlyUnread: true);
      expect((await repository.readList())!.payload['results'], hasLength(1));
      expect(await repository.loadMore(onlyUnread: true), true);
      expect(
        (await repository.readList(onlyUnread: true))!.payload['results'],
        hasLength(30),
      );
      expect(
        requests.where((u) => u.queryParameters['filter'] == 'unread'),
        hasLength(2),
      );
      await repository.markRead('unread-0');
      final remaining = (await repository.readList(onlyUnread: true))!.payload;
      expect(remaining['results'], hasLength(29));
      expect(remaining['count'], 29);
      await repository.markAllRead();
      expect(
        (await repository.readList(onlyUnread: true))!.payload['results'],
        isEmpty,
      );
    },
  );

  test('rejects a continuation that points to another owner path', () async {
    final repository = repositoryFor((request) async {
      return MockResponse(
        jsonEncode({
          'count': 16,
          'next':
              'https://other.invalid/api/v1/accounts/private/?cursor=foreign',
          'results': [
            {'id': 'notification-1', 'is_read': false},
          ],
        }),
        200,
      );
    });
    await repository.refreshList();
    await expectLater(repository.loadMore(), throwsFormatException);
  });
}
