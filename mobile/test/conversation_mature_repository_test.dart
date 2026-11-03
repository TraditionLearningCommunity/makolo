import 'dart:convert';

import 'package:flutter/material.dart';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/features/continuity/conversation_screens.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';
import 'support/presentation_harness.dart';

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
        throw StateError('Unexpected request ${request.url.path}');
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
        throw StateError('Unexpected request ${request.url.path}');
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
  testWidgets('C1: failed first list load finishes with an actionable error', (
    tester,
  ) async {
    final repository = repositoryFor(
      (_) async => MockResponse('{"code":"server_error"}', 500),
    );

    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 150)),
    );
    await tester.pump();

    expect(find.byType(MakoloLoadingState), findsNothing);
    expect(find.byType(MakoloErrorState), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('C1: failed first detail load finishes with an actionable error', (
    tester,
  ) async {
    final repository = repositoryFor(
      (_) async => MockResponse('{"code":"server_error"}', 500),
    );
    await PresentationHarness.pump(
      tester,
      child: ConversationDetailScreen(
        repository: repository,
        id: 'conversation-1',
      ),
    );
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 150)),
    );
    await tester.pump();

    expect(find.byType(MakoloLoadingState), findsNothing);
    expect(find.byType(MakoloErrorState), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('C1: invitations fail independently of the conversation list', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/') {
        return MockResponse(
          jsonEncode({
            'count': 1,
            'results': [
              {
                'id': 'conversation-1',
                'title': 'Départ pour Kolwezi',
                'purpose': 'Coordination du départ',
                'lifecycle': 'active',
                'context': {'kind': 'activity', 'label': 'Transport'},
                'attention_count': 0,
                'latest_result': 'Départ confirmé',
                'all_clear': true,
                'updated_at': '2026-11-04T10:00:00Z',
              },
            ],
          }),
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/invitations/') {
        return MockResponse('{"code":"server_error"}', 500);
      }
      throw StateError('Unexpected request');
    });

    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 150)),
    );
    await tester.pump();

    expect(find.text('Départ pour Kolwezi'), findsOneWidget);
    expect(find.text('Départ confirmé'), findsOneWidget);
    expect(find.textContaining('Invitations non actualisées'), findsOneWidget);
    expect(find.byType(MakoloErrorState), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('C1: an empty collection still shows pending invitations', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/') {
        return MockResponse('{"results":[],"count":0}', 200);
      }
      if (request.url.path == '/api/v1/conversations/invitations/') {
        return MockResponse(
          jsonEncode({
            'count': 1,
            'results': [
              {
                'id': 'invitation-1',
                'conversation_id': 'conversation-1',
                'status': 'pending',
                'expires_at': '2028-01-01T00:00:00Z',
                'created_at': '2026-11-04T00:00:00Z',
              },
            ],
          }),
          200,
        );
      }
      throw StateError('Unexpected request');
    });

    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 150)),
    );
    await tester.pump();

    expect(find.text('Invitations'), findsOneWidget);
    expect(find.text('Accepter'), findsOneWidget);
    expect(find.byType(MakoloErrorState), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('C1: offline snapshots persist, but owner revocation withdraws them', (
    tester,
  ) async {
    var status = 200;
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/') {
        if (status != 200) {
          return MockResponse('{"code":"remote_error"}', status);
        }
        return MockResponse(
          jsonEncode({
            'results': [
              {
                'id': 'conversation-1',
                'title': 'Échange privé',
                'purpose': 'Suivi',
                'context': {'kind': 'space', 'label': 'Équipe'},
                'lifecycle': 'active',
                'attention_count': 0,
                'latest_result': null,
                'all_clear': false,
                'updated_at': '2026-11-04T00:00:00Z',
              },
            ],
            'count': 1,
          }),
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/invitations/') {
        return MockResponse('{"results":[],"count":0}', 200);
      }
      throw StateError('Unexpected request');
    });
    await repository.refreshList();
    status = 500;

    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.tap(find.byTooltip('Actualiser'));
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 150)),
    );
    await tester.pump();
    expect(find.text('Échange privé'), findsOneWidget);
    expect(find.textContaining('Mise à jour impossible'), findsOneWidget);

    status = 403;
    await tester.tap(find.byTooltip('Actualiser'));
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 150)),
    );
    await tester.pump();
    expect(find.text('Échange privé'), findsNothing);
    expect(await repository.readList(), isNull);
    expect(find.text('Action non disponible'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

}
