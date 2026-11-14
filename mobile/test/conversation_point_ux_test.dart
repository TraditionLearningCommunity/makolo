import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
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

  testWidgets('a poll uses full-row choices and contextual Point actions', (
    tester,
  ) async {
    final sends = <Map<String, dynamic>>[];
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
      dio: MockClient((request) async {
        if (request.url.path == '/api/v1/conversations/conversation-1/') {
          return MockResponse(
            jsonEncode({
              'id': 'conversation-1',
              'title': 'Préparation',
              'context': {'kind': 'activity', 'label': 'Atelier'},
              'points': [
                {
                  'id': 'poll-1',
                  'title': 'Quelle priorité ?',
                  'kind': 'poll',
                  'response_mode': 'single_choice',
                  'lifecycle': 'open',
                  'can_respond': true,
                  'response_window_open': true,
                  'can_resolve': true,
                  'can_close_responses': true,
                  'options': [
                    {'id': 'option-a', 'label': 'Sécurité'},
                    {'id': 'option-b', 'label': 'Organisation'},
                  ],
                  'poll_results': {'response_count': 0, 'counts': {}},
                },
              ],
              'essential': [],
              'composer': {'can_create': false, 'media_kinds': []},
            }),
            200,
          );
        }
        if (request.url.path ==
            '/api/v1/conversations/points/poll-1/respond/') {
          sends.add(Map<String, dynamic>.from(request.data as Map));
          return const MockResponse(
            '{"point_id":"poll-1","id":"response-1","status":"active"}',
            200,
          );
        }
        if (request.url.path == '/api/v1/conversations/') {
          return const MockResponse('{"count":0,"results":[]}', 200);
        }
        throw StateError('Unexpected request ${request.url}');
      }).dio,
    );
    final repository = ConversationRepository(
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
    await repository.refreshDetail('conversation-1');
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: ConversationDetailScreen(
        id: 'conversation-1',
        repository: repository,
      ),
    );
    expect(
      find.byKey(const Key('conversation-poll-choice-option-a')),
      findsOneWidget,
    );
    expect(find.text('Choisir'), findsNothing);
    expect(find.text('0 sélection(s)'), findsNothing);
    expect(find.text('Gérer ce Point'), findsNothing);

    await tester.tap(
      find.byKey(const Key('conversation-point-management-poll-1')),
    );
    await tester.pumpAndSettle();
    expect(find.text('Clore les réponses'), findsOneWidget);
    expect(find.text('Consigner le résultat'), findsOneWidget);
    await tester.tapAt(const Offset(12, 300));
    await tester.pumpAndSettle();

    await tester.ensureVisible(
      find.byKey(const Key('conversation-poll-choice-option-a')),
    );
    await tester.tap(
      find.byKey(const Key('conversation-poll-choice-option-a')),
    );
    await tester.pumpAndSettle();
    expect(sends.length, 1);
    expect(sends.single['value'], 'option-a');
    expect(tester.takeException(), isNull);
  });
}
