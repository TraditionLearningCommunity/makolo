import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';
import 'package:makolo_mobile/features/continuity/history_repository.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  late MakoloDatabase database;
  late ProfileStore store;
  late SyncEngine sync;

  setUp(() {
    database = MakoloDatabase.memory();
  });

  tearDown(() async {
    await database.close();
  });

  Future<void> configure(
    Future<MockResponse> Function(MockRequest request) handler,
  ) async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    store = ProfileStore(database, 'profile-a');
    final client = MockClient(handler);
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: client.dio,
    );
    sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );
  }

  test('PC stores Dossier and Project owner projections without local rebuild', () async {
    await configure((request) async {
      if (request.url.path.endsWith('/dossiers/dossier-1/')) {
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': 'objective.dossier.detail',
              'schema_version': 1,
              'generated_at': '2026-09-30T15:00:00Z',
            },
            'data': {
              'objective': {'title': 'Départ études'},
              'readiness': {
                'state': 'action_required',
                'partial': true,
                'hidden_signal': 'Une dépendance privée influence le résultat',
              },
              'visible_items': [],
              'visible_dependencies': [],
              'personal_responsibilities': [],
              'actor_interventions': [],
              'capabilities': [],
            },
          }),
          200,
        );
      }
      return MockResponse(
        jsonEncode({
          'meta': {
            'projection': 'objective.project.detail',
            'schema_version': 1,
            'generated_at': '2026-09-30T15:00:00Z',
          },
          'data': {
            'horizon': {'title': 'Études 2027'},
            'visible_dossiers': [
              {'id': 'dossier-1', 'title': 'Départ études', 'state': 'active'},
            ],
            'capabilities': [],
          },
        }),
        200,
      );
    });
    final repository = ObjectiveRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await repository.refresh(ObjectiveDepth.dossier, 'dossier-1');
    await repository.refresh(ObjectiveDepth.project, 'project-1');

    final dossier =
        await repository.read(ObjectiveDepth.dossier, 'dossier-1');
    final project =
        await repository.read(ObjectiveDepth.project, 'project-1');
    expect(dossier?.payload['readiness'], isA<Map>());
    expect(project?.payload['visible_dossiers'], isA<List>());
  });

  test('PC preserves History pages as separate owner snapshots', () async {
    await configure((request) async {
      expect(request.url.path, '/api/v1/me/history/');
      expect(request.url.queryParameters['offset'], '0');
      return MockResponse(
        jsonEncode({
          'meta': {
            'projection': 'personal.history',
            'schema_version': 1,
            'generated_at': '2026-09-30T15:00:00Z',
          },
          'data': {
            'items': [
              {
                'kind': 'journey',
                'source': {'kind': 'journey', 'id': 'journey-1'},
                'title': 'Formation',
                'occurred_at': '2026-09-01T10:00:00Z',
                'outcome': {'code': 'completed', 'label': 'Terminée'},
              },
            ],
            'page': {
              'count': 1,
              'offset': 0,
              'limit': 24,
              'has_more': false,
            },
          },
        }),
        200,
      );
    });
    final repository = HistoryRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await repository.refreshPage(offset: 0);

    final page = await repository.readPage(offset: 0);
    expect(page?.resourceKey, 'offset:0:limit:24');
    expect((page?.payload['items'] as List).length, 1);
    final cached = await store.readProjections(HistoryRepository.projectionKind);
    expect(cached, hasLength(1));
  });

  test('PC caches Conversation list and detail exactly from owner', () async {
    await configure((request) async {
      if (request.url.path == '/api/v1/conversations/') {
        return MockResponse(
          jsonEncode({
            'results': [
              {
                'id': 'conversation-1',
                'title': 'Préparer le départ',
                'lifecycle': 'active',
                'context': {'kind': 'journey', 'label': 'Voyage'},
                'attention_count': 1,
                'latest_result': null,
                'all_clear': false,
                'updated_at': '2026-09-30T15:00:00Z',
              },
            ],
            'count': 1,
          }),
          200,
        );
      }
      return MockResponse(
        jsonEncode({
          'id': 'conversation-1',
          'title': 'Préparer le départ',
          'purpose': 'Coordination',
          'lifecycle': 'active',
          'context': {'kind': 'journey', 'label': 'Voyage'},
          'points': [
            {
              'id': 'point-1',
              'response_mode': 'free_text',
              'lifecycle': 'open',
              'importance': 'important',
              'title': 'Confirmer votre horaire',
              'body': '',
              'requires_acknowledgement': false,
              'can_respond': true,
              'attention_reason': 'response_required',
              'section': 'now',
            },
          ],
          'updated_at': '2026-09-30T15:00:00Z',
        }),
        200,
      );
    });
    final repository = ConversationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await repository.refreshList();
    await repository.refreshDetail('conversation-1');

    final list = await repository.readList();
    final detail = await repository.readDetail('conversation-1');
    expect((list?.payload['results'] as List).length, 1);
    expect((detail?.payload['points'] as List).single['can_respond'], true);
  });
}
