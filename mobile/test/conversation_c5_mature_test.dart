import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/conversation_history_screen.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';
import 'package:makolo_mobile/features/continuity/conversation_screens.dart';
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
  tearDown(() async => database.close());

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
    return ConversationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: SyncEngine(
        api: api,
        database: database,
        store: store,
        profileId: 'profile-a',
      ),
    );
  }

  Map<String, dynamic> point(String id, {String? title}) => {
    'id': id,
    'title': title ?? 'Point $id',
    'kind': 'information',
    'body': 'Contenu accessible',
    'lifecycle': 'resolved',
    'resolution_summary': 'Résultat vérifié',
    'attachments': [],
  };

  test('C5: signed pagination preserves owner query and section', () async {
    final calls = <Uri>[];
    final repository = repositoryFor((request) async {
      calls.add(request.url);
      if (request.url.path == '/api/v1/conversations/conversation-1/points/') {
        final cursor = request.url.queryParameters['cursor'];
        if (cursor == null) {
          return MockResponse(
            jsonEncode({
              'results': [point('a')],
              'next_cursor': 'owner-signed-token',
              'section': 'all',
            }),
            200,
          );
        }
        expect(cursor, 'owner-signed-token');
        expect(request.url.queryParameters['q'], 'préparation');
        expect(request.url.queryParameters['section'], 'all');
        return MockResponse(
          jsonEncode({
            'results': [point('b')],
            'next_cursor': null,
            'section': 'all',
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    final first = await repository.pointDepth(
      conversationId: 'conversation-1',
      section: 'all',
      query: 'préparation',
      limit: 1,
    );
    final second = await repository.pointDepth(
      conversationId: 'conversation-1',
      section: 'all',
      query: 'préparation',
      limit: 1,
      cursor: first['next_cursor']?.toString(),
    );
    expect((second['results'] as List).single['id'], 'b');
    expect(calls.length, 2);
  });

  test(
    'C5: explicit owner refusal erases cached Point depth and detail',
    () async {
      final repository = repositoryFor((request) async {
        if (request.url.path ==
            '/api/v1/conversations/conversation-1/points/') {
          return const MockResponse('{"detail":"Forbidden"}', 403);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await store.putProjection(
        kind: ConversationRepository.depthProjectionKind,
        resourceKey: 'conversation-1',
        schemaVersion: 1,
        payload: {
          'results': [point('private')],
          'next_cursor': null,
        },
      );
      await store.putProjection(
        kind: ConversationRepository.detailProjectionKind,
        resourceKey: 'conversation-1',
        schemaVersion: 1,
        payload: {
          'id': 'conversation-1',
          'title': 'Privé',
          'points': [point('private')],
        },
      );
      await expectLater(
        repository.pointDepth(conversationId: 'conversation-1'),
        throwsA(isA<Exception>()),
      );
      expect(await repository.readPointDepth('conversation-1'), isNull);
      expect(await repository.readDetail('conversation-1'), isNull);
    },
  );

  test(
    'C5: confirmed invitation is removed locally even if refresh fails',
    () async {
      final repository = repositoryFor((request) async {
        if (request.url.path.endsWith('/invitation-1/respond/')) {
          return const MockResponse(
            '{"id":"invitation-1","conversation_id":"conversation-1","status":"accepted"}',
            200,
          );
        }
        return const MockResponse('{"detail":"offline"}', 500);
      });
      await store.putProjection(
        kind: ConversationRepository.invitationsProjectionKind,
        schemaVersion: 1,
        payload: {
          'results': [
            {'id': 'invitation-1', 'status': 'pending'},
          ],
          'count': 1,
        },
      );
      final opened = await repository.respondToInvitation(
        invitationId: 'invitation-1',
        accept: true,
      );
      expect(opened, 'conversation-1');
      final after = await repository.readInvitations();
      expect(after!.payload['results'], isEmpty);
    },
  );

  test(
    'C5: confirmed personal state remains correct when next GET fails',
    () async {
      final repository = repositoryFor((request) async {
        if (request.url.path.endsWith('/personal-state/')) {
          return const MockResponse(
            '{"conversation_id":"conversation-1","muted":true,'
            '"hidden":false,"archived":true,"pinned":false,"revisit":false}',
            200,
          );
        }
        return const MockResponse('{"detail":"temporary"}', 500);
      });
      await store.putProjection(
        kind: ConversationRepository.detailProjectionKind,
        resourceKey: 'conversation-1',
        schemaVersion: 1,
        payload: {
          'id': 'conversation-1',
          'title': 'Coordination',
          'points': [],
          'personal_state': {'muted': false, 'archived': false},
        },
      );
      await store.putProjection(
        kind: ConversationRepository.listProjectionKind,
        schemaVersion: 1,
        payload: {
          'count': 1,
          'results': [
            {'id': 'conversation-1', 'title': 'Coordination'},
          ],
        },
      );
      await repository.updatePersonalState(
        conversationId: 'conversation-1',
        mute: true,
        archived: true,
      );
      final local = await repository.readDetail('conversation-1');
      expect((local!.payload['personal_state'] as Map)['muted'], true);
      expect((local.payload['personal_state'] as Map)['archived'], true);
      expect((await repository.readList())!.payload['results'], isEmpty);
    },
  );

  testWidgets('C5: history cursor, search and focused Point remain usable', (
    tester,
  ) async {
    final requests = <Uri>[];
    String? opened;
    final repository = repositoryFor((request) async {
      requests.add(request.url);
      if (request.url.path == '/api/v1/conversations/conversation-1/points/') {
        if (request.url.queryParameters['q'] == 'résultat') {
          return MockResponse(
            jsonEncode({
              'results': [point('found', title: 'Résultat recherché')],
              'next_cursor': null,
            }),
            200,
          );
        }
        if (request.url.queryParameters['cursor'] == 'next-owned') {
          return MockResponse(
            jsonEncode({
              'results': [point('next')],
              'next_cursor': null,
            }),
            200,
          );
        }
        return MockResponse(
          jsonEncode({
            'results': [point('first')],
            'next_cursor': 'next-owned',
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await PresentationHarness.pump(
      tester,
      child: ConversationHistoryScreen(
        repository: repository,
        conversationId: 'conversation-1',
        onOpenPoint: (id) => opened = id,
      ),
    );
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump();
    expect(
      find.byKey(const Key('conversation-history-point-first')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('conversation-history-more')));
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump();
    expect(
      requests.any((uri) => uri.queryParameters['cursor'] == 'next-owned'),
      true,
    );
    await tester.enterText(
      find.byKey(const Key('conversation-history-search')),
      'résultat',
    );
    await tester.pump(const Duration(milliseconds: 400));
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump();
    expect(find.text('Résultat recherché'), findsOneWidget);
    await tester.tap(find.text('Résultat recherché'));
    expect(opened, 'found');
  });

  testWidgets(
    'C5: history layout works compact, medium, wide, dark and text 1.6',
    (tester) async {
      final repository = repositoryFor((request) async {
        if (request.url.path.endsWith('/points/')) {
          return MockResponse(
            jsonEncode({
              'results': [
                point(
                  'one',
                  title: 'Départ pour une préparation partagée à Kolwezi',
                ),
              ],
              'next_cursor': null,
            }),
            200,
          );
        }
        throw StateError('Unexpected request ${request.url}');
      });
      for (final dimensions in <Size>[
        const Size(360, 800),
        const Size(430, 932),
        const Size(834, 1112),
        const Size(1440, 900),
      ]) {
        await PresentationHarness.pump(
          tester,
          viewport: dimensions,
          textScale: 1.6,
          brightness: dimensions.width > 800
              ? Brightness.dark
              : Brightness.light,
          reduceMotion: true,
          child: ConversationHistoryScreen(
            key: ValueKey('history-${dimensions.width}'),
            repository: repository,
            conversationId: 'conversation-1',
            onOpenPoint: (_) {},
          ),
        );
        await tester.runAsync(
          () async => Future<void>.delayed(const Duration(milliseconds: 100)),
        );
        await tester.pump();
        expect(
          tester.takeException(),
          isNull,
          reason:
              'History overflow at ${dimensions.width}x${dimensions.height}',
        );
        expect(
          find.byKey(const Key('conversation-history-search')),
          findsOneWidget,
        );
      }
    },
  );

  testWidgets('Space inbox uses only the canonical owner context lookup', (
    tester,
  ) async {
    final paths = <String>[];
    final repository = repositoryFor((request) async {
      paths.add(request.url.path);
      if (request.url.path ==
          '/api/v1/conversations/by-context/space/space-a/') {
        return MockResponse(
          jsonEncode({
            'results': [
              {
                'id': 'context-conversation-a',
                'title': 'Coordination atelier',
                'context': {'kind': 'space', 'label': 'Atelier'},
                'updated_at': '2026-11-09T10:00:00Z',
              },
            ],
          }),
          200,
        );
      }
      throw StateError('A personal or foreign Conversation was requested');
    });
    String? opened;
    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(
        repository: repository,
        spaceId: 'space-a',
        onOpen: (id) => opened = id,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Échanges liés à cet Espace'), findsOneWidget);
    expect(find.text('Coordination atelier'), findsOneWidget);
    expect(find.byKey(const Key('conversation-tab-all')), findsNothing);
    expect(paths, ['/api/v1/conversations/by-context/space/space-a/']);
    await tester.tap(find.text('Coordination atelier'));
    expect(opened, 'context-conversation-a');
  });

  testWidgets('Space inbox permission failure never shows the personal cache', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path ==
          '/api/v1/conversations/by-context/space/space-a/') {
        return const MockResponse('{"detail":"Accès refusé"}', 403);
      }
      throw StateError('Unexpected personal request');
    });
    await store.putProjection(
      kind: ConversationRepository.listProjectionKind,
      schemaVersion: 1,
      payload: {
        'results': [
          {'id': 'personal-private', 'title': 'Privé personnel'},
        ],
        'count': 1,
      },
    );
    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(
        repository: repository,
        spaceId: 'space-a',
        onOpen: (_) {},
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Privé personnel'), findsNothing);
    expect(
      find.text('Conversations de cet Espace indisponibles.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'C5: archived conversations are accessible without fabricating unread counts',
    (tester) async {
      final repository = repositoryFor((request) async {
        if (request.url.path == '/api/v1/conversations/?' ||
            request.url.path == '/api/v1/conversations/') {
          if (request.url.queryParameters['tab'] == 'archived') {
            return MockResponse(
              jsonEncode({
                'results': [
                  {
                    'id': 'archived-1',
                    'title': 'Ancienne coordination',
                    'attention_count': 0,
                  },
                ],
                'count': 1,
              }),
              200,
            );
          }
          return const MockResponse('{"results":[],"count":0}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await repository.refreshList();
      await PresentationHarness.pump(
        tester,
        child: ConversationListScreen(repository: repository, onOpen: (_) {}),
      );
      await tester.tap(find.byKey(const Key('conversation-tab-archived')));
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 100)),
      );
      await tester.pump();
      expect(find.text('Ancienne coordination'), findsOneWidget);
    },
  );

  testWidgets(
    'C5: attention panel keeps expansion state separate from scroll offset',
    (tester) async {
      final repository = repositoryFor((request) async {
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return const MockResponse(
            '{"id":"conversation-1","title":"Coordination",'
            '"points":[],"essential":[],"composer":{"can_create":false,'
            '"media_kinds":[]},'
            '"attention":{"action_count":1,'
            '"for_me":[{"id":"point-1","label":"Action en cours"}],'
            '"to_resolve":[],"to_know":[]}}',
            200,
          );
        }
        throw StateError('Unexpected request');
      });
      await repository.refreshDetail('conversation-1');
      await PresentationHarness.pump(
        tester,
        child: ConversationDetailScreen(
          id: 'conversation-1',
          repository: repository,
          onOpenHistory: () {},
        ),
      );
      await tester.tap(find.textContaining('À présent · 1 action'));
      await tester.pumpAndSettle();
      expect(find.text('Action en cours'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('C5: closed Conversation does not display a composer', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/conversation-1/') {
        return const MockResponse(
          '{"id":"conversation-1","title":"Clôturée","lifecycle":"closed",'
          '"points":[],"essential":[],"composer":{"can_create":false,"media_kinds":[]}}',
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
        onOpenHistory: () {},
      ),
    );
    expect(find.byKey(const Key('conversation-compose-send')), findsNothing);
    expect(find.byKey(const Key('conversation-open-history')), findsOneWidget);
  });
  testWidgets(
    'C5: confirmed publication reacquires and focuses a Point absent from summary groups',
    (tester) async {
      final requests = <Uri>[];
      var confirmed = false;
      final repository = repositoryFor((request) async {
        requests.add(request.url);
        if (request.url.path == '/api/v1/conversations/conv-focus/compose/') {
          confirmed = true;
          return const MockResponse(
            '{"kind":"point","id":"point-new","point_id":"point-new"}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/conv-focus/') {
          return MockResponse(
            jsonEncode({
              'id': 'conv-focus',
              'title': 'Coordination',
              'context': {'kind': 'activity', 'label': 'Départ'},
              'points': [],
              'essential': [],
              'elsewhere': [],
              'focused_point':
                  confirmed &&
                      request.url.queryParameters['focus_point'] == 'point-new'
                  ? {
                      'id': 'point-new',
                      'title': 'Point confirmé',
                      'kind': 'information',
                      'response_mode': 'none',
                      'lifecycle': 'open',
                      'can_respond': false,
                      'section': 'focus',
                      'options': [],
                    }
                  : null,
              'composer': {
                'can_create': true,
                'allowed_kinds': ['information'],
                'text_mode': 'information',
                'audience_selection_required': false,
                'audiences': [],
                'media_kinds': [],
              },
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return const MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await repository.refreshDetail('conv-focus');
      await PresentationHarness.pump(
        tester,
        child: ConversationDetailScreen(
          id: 'conv-focus',
          repository: repository,
        ),
      );
      final editor = find.byKey(const Key('conversation-compose-text'));
      await tester.ensureVisible(editor);
      await tester.enterText(editor, 'Nouvel état confirmé');
      await tester.tap(find.byKey(const Key('conversation-compose-send')));
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 180)),
      );
      await tester.pump();
      expect(
        requests.any(
          (url) =>
              url.path == '/api/v1/conversations/conv-focus/' &&
              url.queryParameters['focus_point'] == 'point-new',
        ),
        isTrue,
      );
      expect(find.text('Point confirmé'), findsOneWidget);
    },
  );
  testWidgets('C5: received invitations open from the Conversations header', (
    tester,
  ) async {
    final repository = repositoryFor((request) async {
      if (request.url.path == '/api/v1/conversations/invitations/') {
        return const MockResponse(
          '{"count":1,"results":[{"id":"invitation-1",'
          '"conversation_id":"conversation-1","status":"pending"}]}',
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/') {
        return const MockResponse('{"count":0,"results":[]}', 200);
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await store.putProjection(
      kind: ConversationRepository.listProjectionKind,
      schemaVersion: 1,
      payload: {'count': 0, 'results': []},
    );
    await store.putProjection(
      kind: ConversationRepository.invitationsProjectionKind,
      schemaVersion: 1,
      payload: {
        'count': 1,
        'results': [
          {
            'id': 'invitation-1',
            'conversation_id': 'conversation-1',
            'status': 'pending',
            'invited_by': 'organisateur',
          },
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.pump();
    final entry = find.byKey(const Key('conversation-invitations-open'));
    expect(entry, findsOneWidget);
    expect(find.byTooltip('Actualiser'), findsOneWidget);
    await tester.tap(entry);
    await tester.pumpAndSettle();
    expect(find.byTooltip('Actualiser les invitations'), findsOneWidget);
    expect(find.text('Accepter'), findsWidgets);
    expect(find.text('Refuser'), findsWidgets);
    expect(find.text('Envoyée par @organisateur'), findsOneWidget);
  });

  testWidgets('C5: one inbox shows managed requests and sent invitations', (
    tester,
  ) async {
    var cancelled = false;
    final repository = repositoryFor((request) async {
      if (request.url.path ==
          '/api/v1/conversations/conv-1/invitations/sent-1/cancel/') {
        cancelled = true;
        return const MockResponse('{"id":"sent-1","status":"cancelled"}', 200);
      }
      if (request.url.path == '/api/v1/conversations/conv-1/') {
        return const MockResponse('{"id":"conv-1","points":[]}', 200);
      }
      if (request.url.path == '/api/v1/conversations/invitations/') {
        return MockResponse(
          jsonEncode({
            'count': 0,
            'results': [],
            'collective_results': [],
            'join_requests_to_decide': [
              {
                'id': 'join-1',
                'conversation_id': 'conv-1',
                'identifier': 'demandeur',
                'can_approve': false,
                'status': 'pending',
              },
            ],
            'sent_results': cancelled
                ? []
                : [
                    {
                      'id': 'sent-1',
                      'conversation_id': 'conv-1',
                      'identifier': 'destinataire',
                      'kind': 'profile',
                      'status': 'pending',
                    },
                  ],
            'my_join_requests': [],
          }),
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/') {
        return const MockResponse('{"count":0,"results":[]}', 200);
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await store.putProjection(
      kind: ConversationRepository.listProjectionKind,
      schemaVersion: 1,
      payload: {'count': 0, 'results': []},
    );
    await store.putProjection(
      kind: ConversationRepository.invitationsProjectionKind,
      schemaVersion: 1,
      payload: {
        'count': 0,
        'results': [],
        'join_requests_to_decide': [
          {
            'id': 'join-1',
            'conversation_id': 'conv-1',
            'identifier': 'demandeur',
            'can_approve': false,
            'status': 'pending',
          },
        ],
        'sent_results': [
          {
            'id': 'sent-1',
            'conversation_id': 'conv-1',
            'identifier': 'destinataire',
            'kind': 'profile',
            'status': 'pending',
          },
        ],
        'my_join_requests': [],
      },
    );
    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.tap(find.byKey(const Key('conversation-invitations-open')));
    await tester.pumpAndSettle();
    expect(find.text('Demandes à examiner'), findsOneWidget);
    expect(find.text('@demandeur'), findsOneWidget);
    expect(find.text('Invitations envoyées'), findsOneWidget);
    expect(find.text('@destinataire'), findsOneWidget);
    // The requester lost eligibility: rejection remains possible but
    // approval is never advertised by the local presentation.
    expect(find.text('Accepter'), findsNothing);
    final cancel = find.text('Annuler l’invitation');
    await tester.ensureVisible(cancel);
    await tester.tap(cancel);
    await tester.pumpAndSettle();
    expect(cancelled, isTrue);
    expect(find.text('@destinataire'), findsNothing);
  });

  test(
    'C5: malformed invitation decision is never reported as accepted',
    () async {
      final repository = repositoryFor((request) async {
        if (request.url.path.endsWith('/invitation-1/respond/')) {
          return const MockResponse(
            '{"id":"invitation-1","status":"pending"}',
            200,
          );
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await store.putProjection(
        kind: ConversationRepository.invitationsProjectionKind,
        schemaVersion: 1,
        payload: {
          'count': 1,
          'results': [
            {'id': 'invitation-1', 'status': 'pending'},
          ],
        },
      );
      await expectLater(
        repository.respondToInvitation(
          invitationId: 'invitation-1',
          accept: true,
        ),
        throwsA(isA<FormatException>()),
      );
      expect(
        (await repository.readInvitations())!.payload['results'],
        isNotEmpty,
      );
    },
  );

  testWidgets('C5: my pending request can be withdrawn without detail access', (
    tester,
  ) async {
    var withdrawn = false;
    final repository = repositoryFor((request) async {
      if (request.url.path ==
          '/api/v1/conversations/join-requests/request-1/withdraw/') {
        withdrawn = true;
        return const MockResponse(
          '{"id":"request-1","status":"cancelled"}',
          200,
        );
      }
      if (request.url.path == '/api/v1/conversations/invitations/') {
        // A refresh failure cannot undo the confirmed withdrawal.
        return const MockResponse('{"detail":"temporary"}', 500);
      }
      if (request.url.path == '/api/v1/conversations/') {
        return const MockResponse('{"count":0,"results":[]}', 200);
      }
      throw StateError('Unexpected request ${request.url}');
    });
    await store.putProjection(
      kind: ConversationRepository.listProjectionKind,
      schemaVersion: 1,
      payload: {'count': 0, 'results': []},
    );
    await store.putProjection(
      kind: ConversationRepository.invitationsProjectionKind,
      schemaVersion: 1,
      payload: {
        'count': 0,
        'results': [],
        'my_join_requests': [
          {'id': 'request-1', 'conversation_id': null, 'status': 'pending'},
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      child: ConversationListScreen(repository: repository, onOpen: (_) {}),
    );
    await tester.tap(find.byKey(const Key('conversation-invitations-open')));
    await tester.pumpAndSettle();
    expect(find.text('Mes demandes d’entrée'), findsOneWidget);
    expect(find.text('Voir ma demande'), findsNothing);
    final withdraw = find.text('Retirer ma demande');
    await tester.ensureVisible(withdraw);
    await tester.tap(withdraw);
    await tester.pumpAndSettle();
    expect(withdrawn, isTrue);
    expect(find.text('Retirer ma demande'), findsNothing);
    expect(
      (await repository.readInvitations())!.payload['my_join_requests'],
      isEmpty,
    );
  });

  test(
    'C5: wrong join withdrawal ACK preserves unconfirmed local request',
    () async {
      final repository = repositoryFor((request) async {
        if (request.url.path.endsWith('/request-1/withdraw/')) {
          return const MockResponse(
            '{"id":"request-1","status":"pending"}',
            200,
          );
        }
        throw StateError('Unexpected request ${request.url}');
      });
      await store.putProjection(
        kind: ConversationRepository.invitationsProjectionKind,
        schemaVersion: 1,
        payload: {
          'count': 0,
          'results': [],
          'my_join_requests': [
            {'id': 'request-1', 'status': 'pending'},
          ],
        },
      );
      await expectLater(
        repository.withdrawJoinRequest('request-1'),
        throwsA(isA<FormatException>()),
      );
      expect(
        (await repository.readInvitations())!.payload['my_join_requests'],
        isNotEmpty,
      );
    },
  );
}
