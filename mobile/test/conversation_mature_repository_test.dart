import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/features/continuity/conversation_screens.dart';
import 'package:makolo_mobile/features/continuity/conversation_point_presentation.dart';
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

  testWidgets(
    'C1: failed first detail load finishes with an actionable error',
    (tester) async {
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
    },
  );

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
    expect(find.textContaining('Départ confirmé'), findsOneWidget);
    expect(
      find.textContaining('Impossible d’actualiser les invitations'),
      findsOneWidget,
    );
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

  testWidgets(
    'C1: offline snapshots persist, but owner revocation withdraws them',
    (tester) async {
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
    },
  );

  test('C2: search and context lookup use real owner endpoints', () async {
    final requests = <Uri>[];
    final repository = repositoryFor((request) async {
      requests.add(request.url);
      if (request.url.path == '/api/v1/conversations/' &&
          request.url.queryParameters['q'] == 'Kolwezi') {
        return MockResponse(
          jsonEncode({
            'count': 1,
            'results': [
              {
                'id': 'conversation-1',
                'title': 'Départ pour Kolwezi',
                'matched_point_id': 'point-1',
                'context': {'kind': 'activity', 'label': 'Transport'},
              },
            ],
          }),
          200,
        );
      }
      if (request.url.path ==
          '/api/v1/conversations/by-context/activity/activity-1/') {
        return MockResponse(
          jsonEncode({
            'count': 1,
            'results': [
              {'id': 'conversation-1', 'title': 'Départ pour Kolwezi'},
            ],
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });

    final search = await repository.searchConversations('Kolwezi');
    expect(search.single['matched_point_id'], 'point-1');
    final context = await repository.conversationsForContext(
      kind: 'activity',
      id: 'activity-1',
    );
    expect(context.single['id'], 'conversation-1');
    expect(requests.length, 2);
    expect(await repository.readList(), isNull);
    expect(
      await repository.conversationsForContext(kind: 'unsupported', id: 'x'),
      isEmpty,
    );
  });

  testWidgets(
    'C2: N1 detail groups distinct Points and offers inline confirmation',
    (tester) async {
      var replied = false;
      final requests = <Uri>[];
      final repository = repositoryFor((request) async {
        requests.add(request.url);
        if (request.url.path ==
            '/api/v1/conversations/points/point-confirm/respond/') {
          final body = request.data as Map;
          expect(body['value'], true);
          replied = true;
          return MockResponse(
            jsonEncode({
              'id': 'response-1',
              'point_id': 'point-confirm',
              'status': 'active',
              'value': true,
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return MockResponse(
            jsonEncode({
              'id': 'conversation-1',
              'title': 'Départ vers Kolwezi',
              'purpose': 'Coordination',
              'context': {'kind': 'activity', 'label': 'Transport'},
              'points': [
                {
                  'id': 'point-confirm',
                  'conversation_id': 'conversation-1',
                  'title': 'Vous confirmez ?',
                  'kind': 'confirmation',
                  'response_mode': 'boolean',
                  'lifecycle': 'open',
                  'requires_acknowledgement': false,
                  'can_respond': !replied,
                  'section': 'pour_moi',
                  'attention_reason': replied ? null : 'respond',
                  'options': [],
                },
              ],
              'essential': [
                {
                  'id': 'point-confirm',
                  'title': 'Vous confirmez ?',
                  'kind': 'confirmation',
                  'response_mode': 'boolean',
                  'lifecycle': 'open',
                  'can_respond': true,
                  'section': 'essential',
                  'options': [],
                },
              ],
              'elsewhere': [
                {
                  'id': 'point-elsewhere',
                  'title': 'Une question en cours',
                  'kind': 'question',
                  'response_mode': 'free_text',
                  'can_respond': false,
                  'lifecycle': 'open',
                  'section': 'elsewhere',
                  'options': [],
                },
              ],
              'focused_point': null,
              'personal_state': {},
              'updated_at': '2026-11-04T00:00:00Z',
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });

      await repository.refreshDetail('conversation-1');
      await PresentationHarness.pump(
        tester,
        child: ConversationDetailScreen(
          repository: repository,
          id: 'conversation-1',
          focusPointId: 'point-confirm',
        ),
      );
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 150)),
      );
      await tester.pump();
      expect(find.text('Départ vers Kolwezi'), findsOneWidget);
      expect(find.text('Vous confirmez ?'), findsOneWidget);
      expect(
        find.byKey(const Key('conversation-detail-content')),
        findsOneWidget,
      );
      // C1_bus no longer makes users navigate through administrative sections.
      expect(find.text('À vous'), findsNothing);
      await tester.tap(find.text('Oui'));
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 150)),
      );
      await tester.pump();
      expect(replied, isTrue);
      expect(
        requests.any(
          (uri) => uri.queryParameters['focus_point'] == 'point-confirm',
        ),
        isTrue,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );

  testWidgets(
    'C1_bus: detail keeps the composer fixed and context accessible',
    (tester) async {
      final repository = repositoryFor((request) async {
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return MockResponse(
            jsonEncode({
              'id': 'conversation-1',
              'title': 'Préparation pratique — Marché des coopératives',
              'purpose': 'Informations sur la préparation du marché.',
              'context': {
                'kind': 'activity',
                'label': 'Marché des coopératives',
              },
              'personal_state': {},
              'points': [
                for (var i = 0; i < 18; i++)
                  {
                    'id': 'point-$i',
                    'title': 'Question $i',
                    'body': 'Information de préparation $i.',
                    'kind': 'information',
                    'response_mode': 'none',
                    'can_respond': false,
                    'section': 'information',
                    'published_at': DateTime.utc(
                      2026,
                      11,
                      4,
                      10,
                      i,
                    ).toIso8601String(),
                  },
              ],
              'essential': [],
              'elsewhere': [],
              'composer': {
                'can_create': true,
                'text_mode': 'information',
                'allowed_kinds': ['information'],
                'audience_selection_required': false,
              },
            }),
            200,
          );
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await repository.refreshDetail('conversation-1');
      await PresentationHarness.pump(
        tester,
        child: ConversationDetailScreen(
          repository: repository,
          id: 'conversation-1',
        ),
      );
      await tester.pump();
      final timeline = find.byKey(const Key('conversation-detail-content'));
      final composer = find.byKey(const Key('conversation-composer'));
      expect(timeline, findsOneWidget);
      expect(composer, findsOneWidget);
      expect(find.text('Préparation pratique'), findsOneWidget);
      expect(find.text('À savoir et résultats'), findsNothing);
      final fixedTop = tester.getTopLeft(composer).dy;
      await tester.drag(timeline, const Offset(0, 320));
      await tester.pump();
      expect(tester.getTopLeft(composer).dy, closeTo(fixedTop, 1));

      await tester.tap(find.byKey(const Key('conversation-context-header')));
      await tester.pumpAndSettle();
      expect(
        find.text('Informations sur la préparation du marché.'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );

  testWidgets(
    'C2_bus: Point author, time, types and media stay in the conversation',
    (tester) async {
      final repository = repositoryFor((request) async {
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return MockResponse(
            jsonEncode({
              'id': 'conversation-1',
              'title': 'Préparation',
              'context': {'kind': 'activity', 'label': 'Marché'},
              'points': [
                {
                  'id': 'photo-point',
                  'title': 'Voici le modèle',
                  'kind': 'information',
                  'response_mode': 'none',
                  'can_respond': false,
                  'author': {
                    'label': 'Marie N.',
                    'is_mine': false,
                    'represented_space': false,
                  },
                  'published_at': '2026-11-05T09:30:00Z',
                  'attachments': [
                    {
                      'id': 'photo-1',
                      'kind': 'image',
                      'name': 'modele.jpg',
                      'mime_type': 'image/jpeg',
                    },
                  ],
                },
                {
                  'id': 'poll-point',
                  'title': 'Quel modèle choisir ?',
                  'kind': 'poll',
                  'response_mode': 'single_choice',
                  'can_respond': false,
                  'author': {
                    'label': 'Organisation',
                    'is_mine': true,
                    'represented_space': true,
                  },
                  'published_at': '2026-11-05T09:35:00Z',
                  'options': [
                    {'id': 'a', 'label': 'Modèle A'},
                    {'id': 'b', 'label': 'Modèle B'},
                  ],
                  'response_status': {'response_count': 0},
                },
              ],
              'elsewhere': [],
              'essential': [],
              'personal_state': {},
              'composer': {},
            }),
            200,
          );
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await repository.refreshDetail('conversation-1');
      await PresentationHarness.pump(
        tester,
        child: ConversationDetailScreen(
          id: 'conversation-1',
          repository: repository,
        ),
      );
      await tester.pump();
      final other = find.byKey(
        const Key('conversation-point-shell-photo-point'),
      );
      final mine = find.byKey(const Key('conversation-point-shell-poll-point'));
      expect(other, findsOneWidget);
      expect(mine, findsOneWidget);
      expect(tester.widget<ConversationPointShell>(other).isMine, isFalse);
      expect(tester.widget<ConversationPointShell>(mine).isMine, isTrue);
      expect(find.text('Marie N.'), findsOneWidget);
      expect(find.text('Vous · Organisation'), findsOneWidget);
      expect(find.text('Sondage'), findsOneWidget);
      expect(find.text('modele.jpg'), findsOneWidget);
      expect(find.text('0 réponse(s)'), findsNothing);
      expect(find.text('0 réponses'), findsNothing);
      expect(
        find.byKey(const Key('conversation-point-attachment-photo-1')),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );

  testWidgets(
    'C2_bus: narrow Point bubble supports enlarged text and dark theme',
    (tester) async {
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        textScale: 1.6,
        brightness: Brightness.dark,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: ConversationPointShell(
            kind: 'confirmation',
            isMine: true,
            authorLabel: 'Coopérative locale de préparation',
            representedSpace: true,
            publishedAt: DateTime.utc(2026, 11, 5, 10, 30),
            child: const Text(
              'Je confirme que les documents et les détails sont disponibles.',
            ),
          ),
        ),
      );
      expect(find.text('Confirmation'), findsOneWidget);
      expect(find.textContaining('Vous ·'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  test('C3: composition sends owner commands, keeps client reference and refreshes', () async {
    final calls = <MockRequest>[];
    final repository = repositoryFor((request) async {
      calls.add(request);
      if (request.url.path == '/api/v1/conversations/conversation-1/compose/') {
        final body = request.data as Map;
        expect(body['mode'], 'point');
        expect(body['kind'], 'poll');
        expect(body['client_reference'], 'c3-fixed-ref');
        expect(body['options'], ['14 h', '15 h']);
        expect(body['audience_id'], 'audience-1');
        return MockResponse(
          '{"kind":"point","id":"point-1","point_id":"point-1"}',
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/conversation-1/') {
        return MockResponse(
          jsonEncode({
            'id': 'conversation-1',
            'title': 'Coordination',
            'points': [],
            'essential': [],
            'composer': {'text_mode': 'information', 'can_create': true},
          }),
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/') {
        return MockResponse('{"count":0,"results":[]}', 200);
      }
      throw StateError('Unexpected request ${request.url}');
    });

    final id = await repository.compose(
      conversationId: 'conversation-1',
      mode: 'point',
      kind: 'poll',
      title: 'Quelle heure ?',
      options: ['14 h', '15 h'],
      audienceId: 'audience-1',
      clientReference: 'c3-fixed-ref',
    );
    expect(id, 'point-1');
    expect(
      calls.map((item) => item.url.path),
      contains('/api/v1/conversations/conversation-1/'),
    );
    expect(
      calls.map((item) => item.url.path),
      contains('/api/v1/conversations/'),
    );
  });

  test(
    'C3: context ensure creates through owner and rejects implicit direct',
    () async {
      final calls = <MockRequest>[];
      final repository = repositoryFor((request) async {
        calls.add(request);
        if (request.url.path ==
            '/api/v1/conversations/by-context/space/space-1/') {
          return MockResponse(
            '{"count":0,"can_ensure":true,"results":[]}',
            200,
          );
        }
        if (request.url.path ==
            '/api/v1/conversations/by-context/space/space-1/ensure/') {
          return MockResponse('{"id":"conversation-new"}', 200);
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      final decision = await repository.contextDecision(
        kind: 'space',
        id: 'space-1',
      );
      expect(decision['can_ensure'], true);
      final id = await repository.ensureContext(kind: 'space', id: 'space-1');
      expect(id, 'conversation-new');
      await expectLater(
        repository.ensureContext(kind: 'direct', id: 'profile-2'),
        throwsStateError,
      );
      expect(
        calls.where((item) => item.url.path.endsWith('/ensure/')).length,
        1,
      );
    },
  );

  testWidgets(
    'C3: inline text is sent once and a failed send retains its draft',
    (tester) async {
      var failFirst = true;
      final sent = <String>[];
      final repository = repositoryFor((request) async {
        if (request.url.path ==
            '/api/v1/conversations/conversation-1/compose/') {
          final body = request.data as Map;
          sent.add(body['client_reference'].toString());
          expect(body['body'], 'Point de coordination');
          if (failFirst) {
            failFirst = false;
            return MockResponse('{"detail":"Temporary failure"}', 500);
          }
          return MockResponse(
            '{"kind":"point","id":"point-1","point_id":"point-1"}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return MockResponse(
            jsonEncode({
              'id': 'conversation-1',
              'title': 'Organisation',
              'purpose': 'Coordination',
              'context': {'kind': 'space', 'label': 'Espace'},
              'points': [],
              'essential': [],
              'elsewhere': [],
              'personal_state': {},
              'composer': {
                'can_create': true,
                'text_mode': 'information',
                'allowed_kinds': ['information', 'poll', 'confirmation'],
                'audience_selection_required': false,
                'audiences': [],
              },
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await repository.refreshDetail('conversation-1');
      await PresentationHarness.pump(
        tester,
        child: ConversationDetailScreen(
          id: 'conversation-1',
          repository: repository,
        ),
      );
      final input = find.byKey(const Key('conversation-compose-text'));
      await tester.ensureVisible(input);
      await tester.enterText(input, 'Point de coordination');
      await tester.tap(find.byKey(const Key('conversation-compose-send')));
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 120)),
      );
      await tester.pump();
      expect(find.text('Point de coordination'), findsOneWidget);
      expect(find.textContaining('Envoi non conservé'), findsOneWidget);
      await tester.tap(find.byKey(const Key('conversation-compose-send')));
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 120)),
      );
      await tester.pump();
      expect(sent.length, 2);
      expect(sent[0], sent[1]);
      expect(find.text('Point de coordination'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );

  testWidgets('C3: Poll shortcut opens a real editor with fields', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/conversation-1/') {
        return MockResponse(
          jsonEncode({
            'id': 'conversation-1',
            'title': 'Organisation',
            'points': [],
            'essential': [],
            'composer': {
              'can_create': true,
              'text_mode': 'information',
              'allowed_kinds': ['poll', 'confirmation', 'information'],
              'audience_selection_required': false,
            },
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await repository.refreshDetail('conversation-1');
    await PresentationHarness.pump(
      tester,
      child: ConversationDetailScreen(
        id: 'conversation-1',
        repository: repository,
      ),
    );
    await tester.tap(find.byKey(const Key('conversation-compose-type')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('conversation-type-information')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('conversation-type-poll')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('conversation-compose-title')), findsOneWidget);
    expect(
      find.byKey(const Key('conversation-compose-options')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('conversation-compose-publish')),
      findsOneWidget,
    );
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  test(
    'C4: FormRequest publishes through owner and refreshes projections',
    () async {
      final calls = <String>[];
      final repository = repositoryFor((request) async {
        calls.add(request.url.path);
        if (request.url.path == '/api/v1/conversations/conv-4/forms/') {
          final payload = request.data as Map;
          expect(payload['title'], 'Préparation');
          expect(payload['questions'], ['Votre matériel ?']);
          expect(payload['audience_id'], 'audience-1');
          expect(payload['client_reference'], 'form-stable-ref');
          return MockResponse(
            '{"id":"point-form","point_id":"point-form","kind":"form_request"}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/conv-4/') {
          return MockResponse(
            '{"id":"conv-4","title":"Coordination","points":[],"essential":[]}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      final id = await repository.publishForm(
        conversationId: 'conv-4',
        title: 'Préparation',
        clientReference: 'form-stable-ref',
        questions: ['Votre matériel ?'],
        audienceId: 'audience-1',
      );
      expect(id, 'point-form');
      expect(calls, contains('/api/v1/conversations/conv-4/'));
      expect(calls, contains('/api/v1/conversations/'));
    },
  );

  test('C4: scoped Exchange pagination consumes only owner result', () async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/points/point-1/entries/') {
        expect(request.url.queryParameters['cursor'], 'entry-cursor');
        return MockResponse(
          jsonEncode({
            'results': [
              {
                'id': 'entry-2',
                'body': 'Message accessible',
                'own': true,
                'attachments': [],
              },
            ],
            'next_cursor': null,
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    final result = await repository.exchangeEntries(
      pointId: 'point-1',
      cursor: 'entry-cursor',
    );
    expect((result['results'] as List).single['body'], 'Message accessible');
    expect(result['next_cursor'], isNull);
  });

  test('C4: media MIME and private media transport are owner-scoped', () async {
    expect(
      ConversationRepository.mediaMime('document.pdf', 'file'),
      'application/pdf',
    );
    expect(ConversationRepository.mediaMime('vocal.m4a', 'voice'), 'audio/mp4');
    expect(ConversationRepository.mediaMime('photo.png', 'image'), 'image/png');
    final requests = <String>[];
    final repository = repositoryFor((request) async {
      requests.add(request.url.path);
      if (request.url.path == '/api/v1/conversations/conv-4/media/') {
        return MockResponse(
          jsonEncode({
            'point_id': 'point-2',
            'attachment': {'id': 'attachment-2', 'kind': 'image'},
          }),
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/conv-4/') {
        return MockResponse(
          '{"id":"conv-4","title":"Coordination","points":[]}',
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/') {
        return MockResponse('{"count":0,"results":[]}', 200);
      }
      throw StateError('Unexpected request ${request.url}');
    });
    // Upload bytes are intentionally tested with the native platform; no
    // widget fabricates a sent state while the owner is unavailable.
    await expectLater(
      repository.downloadAttachment(
        attachmentId: '../unsafe',
        filename: '../file',
      ),
      throwsA(isA<FormatException>()),
    );
  });

  testWidgets('C4: immediate Form editor and real owner button are available', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/conv-4/') {
        return MockResponse(
          jsonEncode({
            'id': 'conv-4',
            'title': 'Préparation',
            'points': [],
            'essential': [],
            'composer': {
              'can_create': true,
              'text_mode': 'information',
              'allowed_kinds': ['information'],
              'can_form': true,
              'form_options': [],
              'media_kinds': ['voice', 'file', 'image'],
              'audience_selection_required': false,
            },
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await repository.refreshDetail('conv-4');
    await PresentationHarness.pump(
      tester,
      child: ConversationDetailScreen(id: 'conv-4', repository: repository),
    );
    await tester.tap(find.byKey(const Key('conversation-compose-type')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('conversation-type-form')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('conversation-form-title')), findsOneWidget);
    expect(
      find.byKey(const Key('conversation-form-questions')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('conversation-form-publish')), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('C4: Point Form Request continues into canonical owner', (
    tester,
  ) async {
    String? opened;
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/conv-4/') {
        return MockResponse(
          jsonEncode({
            'id': 'conv-4',
            'title': 'Coordination',
            'points': [
              {
                'id': 'point-form-1',
                'kind': 'form_request',
                'title': 'Préparation collective',
                'response_mode': 'none',
                'lifecycle': 'open',
                'can_respond': false,
                'requires_acknowledgement': false,
                'options': [],
                'form_request': {
                  'id': 'form-request-1',
                  'status': 'requested',
                  'links': {
                    'detail': 'api/v1/questionnaires/requests/form-request-1/',
                  },
                },
                'section': 'pour_moi',
              },
            ],
            'essential': [],
            'composer': {},
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await repository.refreshDetail('conv-4');
    await PresentationHarness.pump(
      tester,
      child: ConversationDetailScreen(
        id: 'conv-4',
        repository: repository,
        onOpenFormRequest: (requestId) async {
          opened = requestId;
        },
      ),
    );
    await tester.ensureVisible(find.text('Compléter le formulaire'));
    await tester.tap(find.text('Compléter le formulaire'));
    await tester.pump();
    expect(opened, 'form-request-1');
  });

  test('C4: FILE PointResponse upload confirms the existing Point', () async {
    final file = File(
      '${Directory.systemTemp.path}/c4-test-${DateTime.now().microsecondsSinceEpoch}.txt',
    );
    await file.writeAsString('Pièce privée');
    try {
      final requests = <String>[];
      final repository = repositoryFor((request) async {
        requests.add(request.url.path);
        if (request.url.path ==
            '/api/v1/conversations/points/point-4/reply-media/') {
          return MockResponse(
            '{"point_id":"point-4","response_id":"response-4","attachment":{"id":"file-4","kind":"file"}}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/conv-4/') {
          return MockResponse(
            '{"id":"conv-4","points":[],"title":"Coordination"}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      final response = await repository.respondWithMedia(
        conversationId: 'conv-4',
        pointId: 'point-4',
        filePath: file.path,
        filename: 'document.txt',
        kind: 'file',
        clientReference: 'c4-response-stable',
      );
      expect(response['point_id'], 'point-4');
      expect(
        requests.first,
        '/api/v1/conversations/points/point-4/reply-media/',
      );
    } finally {
      if (await file.exists()) await file.delete();
    }
  });

  testWidgets('C4: a FILE Point offers its actual upload action', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/conv-4/') {
        return MockResponse(
          jsonEncode({
            'id': 'conv-4',
            'title': 'Coordination',
            'points': [
              {
                'id': 'point-file',
                'kind': 'request',
                'response_mode': 'file',
                'title': 'Envoyez le document',
                'can_respond': true,
                'lifecycle': 'open',
                'section': 'pour_moi',
                'attention_reason': 'respond',
                'options': [],
                'requires_acknowledgement': false,
              },
            ],
            'essential': [],
            'composer': {},
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await repository.refreshDetail('conv-4');
    await PresentationHarness.pump(
      tester,
      child: ConversationDetailScreen(id: 'conv-4', repository: repository),
    );
    expect(
      find.byKey(const Key('conversation-point-media-point-file')),
      findsOneWidget,
    );
    expect(find.text('Joindre un fichier'), findsOneWidget);
  });

  test(
    'visual N1 image resolver refuses arbitrary URL and preserves owner',
    () {
      final repository = repositoryFor(
        (request) async => const MockResponse('{"results":[],"count":0}', 200),
      );
      expect(
        repository.publicContextImageUri('/media/events/public.jpg').toString(),
        'https://makolo.invalid/media/events/public.jpg',
      );
      expect(
        repository.publicContextImageUri('https://other.invalid/x.jpg'),
        isNull,
      );
      expect(repository.publicContextImageUri('//other.invalid/x.jpg'), isNull);
      expect(
        repository.publicContextImageUri('/media/x.jpg?token=secret'),
        isNull,
      );
      expect(repository.publicContextImageUri(''), isNull);
    },
  );

  testWidgets(
    'visual N1 uses owner card without repeating long context and preserves direct route',
    (tester) async {
      final repository = repositoryFor((request) async {
        if (request.url.path == '/api/v1/conversations/') {
          return MockResponse(
            jsonEncode({
              'results': [
                {
                  'id': 'cooperative-1',
                  'title': 'Préparation pratique — Marché des coopératives — Lubumbashi',
                  'purpose':
                      'Texte administrativement long qui appartient au détail',
                  'context': {
                    'kind': 'activity',
                    'label': 'Marché des coopératives — Lubumbashi',
                  },
                  'attention_count': 2,
                  'all_clear': false,
                  'latest_result': null,
                  'updated_at': '2026-11-04T13:00:00Z',
                  'card': {
                    'title': 'Marché des coopératives',
                    'context_label': 'Lubumbashi',
                    'context_kind': 'activity',
                    'context_image_url': null,
                    'preview': 'Préparer les documents d’accès',
                    'preview_kind': 'point',
                    'media_kinds': ['image', 'form'],
                    'attention_count': 2,
                  },
                },
              ],
              'count': 1,
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/invitations/') {
          return const MockResponse('{"results":[],"count":0}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await repository.refreshList();
      String? opened;
      await PresentationHarness.pump(
        tester,
        child: ConversationListScreen(
          repository: repository,
          onOpen: (id) => opened = id,
        ),
      );
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 100)),
      );
      await tester.pump();
      expect(find.text('Marché des coopératives'), findsOneWidget);
      expect(find.text('Lubumbashi'), findsOneWidget);
      expect(find.textContaining('Préparer les documents'), findsOneWidget);
      expect(find.textContaining('Préparation pratique —'), findsNothing);
      expect(find.byIcon(Icons.image_rounded), findsOneWidget);
      expect(find.byIcon(Icons.assignment_rounded), findsOneWidget);
      expect(find.textContaining('2 à faire'), findsOneWidget);
      await tester.tap(
        find.byKey(const Key('conversation-tile-cooperative-1')),
      );
      expect(opened, 'cooperative-1');
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
