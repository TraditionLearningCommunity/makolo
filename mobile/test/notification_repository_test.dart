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
        throw StateError('Unexpected request ' + request.url.path);
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
      throw StateError('Unexpected request ' + request.url.path);
    });

    await repository.refreshPreferences();
    await repository.updatePreferences({'push_notifications': false});

    final stored = await repository.readPreferences();
    expect(stored?.payload['push_notifications'], false);
  });
}
