import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
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

  ConversationRepository repositoryFor(
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
    return ConversationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
  }

  test(
    'Point response waits for owner confirmation and reprojections',
    () async {
      var responded = false;
      final requests = <String>[];
      final repository = repositoryFor((request) async {
        requests.add(request.url.path);
        if (request.url.path ==
            '/api/v1/conversations/points/point-1/respond/') {
          final body = request.data as Map;
          expect(body['client_reference'], 'stable-client-ref');
          expect(body['represented_space_id'], 'space-1');
          responded = true;
          return MockResponse(
            jsonEncode({
              'id': 'response-1',
              'point_id': 'point-1',
              'status': 'active',
              'value': true,
              'submitted_at': '2026-10-09T09:00:00Z',
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return MockResponse(
            jsonEncode({
              'id': 'conversation-1',
              'title': 'Coordination',
              'lifecycle': 'active',
              'context': {'kind': 'space', 'label': 'Mulykap'},
              'points': responded
                  ? []
                  : [
                      {
                        'id': 'point-1',
                        'response_mode': 'boolean',
                        'lifecycle': 'open',
                        'importance': 'important',
                        'title': 'Confirmer ?',
                        'body': '',
                        'requires_acknowledgement': false,
                        'can_respond': true,
                        'options': [],
                        'attention_reason': 'respond',
                        'section': 'pour_moi',
                      },
                    ],
              'essential': [],
              'personal_state': {
                'muted': false,
                'hidden': false,
                'archived': false,
                'pinned': false,
                'revisit': false,
              },
              'updated_at': '2026-10-09T09:00:00Z',
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse(
            jsonEncode({
              'results': [
                {
                  'id': 'conversation-1',
                  'title': 'Coordination',
                  'lifecycle': 'active',
                  'context': {'kind': 'space', 'label': 'Mulykap'},
                  'attention_count': responded ? 0 : 1,
                  'latest_result': null,
                  'all_clear': responded,
                  'updated_at': '2026-10-09T09:00:00Z',
                },
              ],
              'count': 1,
            }),
            200,
          );
        }
        throw StateError('Unexpected request ' + request.url.path);
      });

      await repository.respondToPoint(
        conversationId: 'conversation-1',
        pointId: 'point-1',
        value: true,
        clientReference: 'stable-client-ref',
        representedSpaceId: 'space-1',
      );

      expect(requests.first, '/api/v1/conversations/points/point-1/respond/');
      expect(requests, contains('/api/v1/conversations/conversation-1/'));
      expect(requests, contains('/api/v1/conversations/'));
      final detail = await repository.readDetail('conversation-1');
      expect((detail?.payload['points'] as List), isEmpty);
    },
  );

  test(
    'invitation decision refreshes invitation and conversation owners',
    () async {
      var accepted = false;
      final repository = repositoryFor((request) async {
        if (request.url.path ==
            '/api/v1/conversations/invitations/invitation-1/respond/') {
          accepted = true;
          return MockResponse(
            jsonEncode({
              'id': 'invitation-1',
              'conversation_id': 'conversation-1',
              'status': 'accepted',
              'responded_at': '2026-10-09T09:00:00Z',
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/invitations/') {
          return MockResponse(
            jsonEncode({
              'results': accepted
                  ? []
                  : [
                      {
                        'id': 'invitation-1',
                        'conversation_id': 'conversation-1',
                        'status': 'pending',
                        'expires_at': '2026-10-10T09:00:00Z',
                        'created_at': '2026-10-09T08:00:00Z',
                      },
                    ],
              'count': accepted ? 0 : 1,
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse(
            jsonEncode({'results': const [], 'count': 0}),
            200,
          );
        }
        throw StateError('Unexpected request ' + request.url.path);
      });

      await repository.refreshInvitations();
      final conversationId = await repository.respondToInvitation(
        invitationId: 'invitation-1',
        accept: true,
      );

      expect(conversationId, 'conversation-1');
      final invitations = await repository.readInvitations();
      expect((invitations?.payload['results'] as List), isEmpty);
    },
  );
}
