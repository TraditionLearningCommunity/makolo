import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/history_repository.dart';
import 'package:makolo_mobile/features/continuity/history_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

Map<String, dynamic> _page({
  required String query,
  required String type,
  String title = 'Accès retrouvé du serveur',
  int offset = 0,
  bool hasMore = false,
}) => {
  'filter': type,
  'query': query.isEmpty ? null : query,
  'items': [
    {
      'kind': 'access',
      'source': {'kind': 'access', 'id': 'access-$offset'},
      'title': title,
      'occurred_at': '2026-10-10T13:00:00Z',
      'time_quality': 'owner_event',
      'outcome': {'code': 'used', 'label': 'Utilisé'},
      'capabilities': ['view_detail'],
    },
  ],
  'page': {'offset': offset, 'limit': 24, 'has_more': hasMore},
  'coverage': {
    'state': 'partial',
    'owners': ['access', 'journey'],
  },
};

class _OwnerApi implements MakoloApiClient {
  bool offline = false;
  int totalPages = 1;
  int calls = 0;
  @override
  Uri get baseUri => Uri.parse('https://makolo.test/');

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    calls++;
    if (offline) throw StateError('offline');
    final uri = Uri.parse(path);
    final query = uri.queryParameters['q'] ?? '';
    final type = uri.queryParameters['type'] ?? 'all';
    final offset = int.tryParse(uri.queryParameters['offset'] ?? '0') ?? 0;
    return ApiResponse(
      200,
      jsonEncode({
        'meta': {
          'projection': HistoryRepository.projectionKind,
          'schema_version': 1,
          'scope': 'personal',
          'generated_at': DateTime.now().toUtc().toIso8601String(),
        },
        'data': _page(
          query: query,
          type: type,
          offset: offset,
          hasMore: offset ~/ 24 < totalPages - 1,
        ),
      }),
      const {'cache-control': 'private, no-store'},
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test(
    'server History search survives restart in its own Profile and scope',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final api = _OwnerApi();
      final repo = HistoryRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: SyncEngine(
          api: api,
          store: store,
          database: db,
          profileId: 'profile-a',
        ),
      );
      await repo.searchPage(query: 'trajet', type: 'accesses');
      api.offline = true;
      final offline = HistoryRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
      );
      final copies = await offline.readCachedSearchPages(
        query: 'trajet',
        type: 'accesses',
      );
      expect(copies, hasLength(1));
      expect(copies.single.payload['items'], isNotEmpty);
      expect(
        await offline.readCachedSearchPages(query: 'autre', type: 'accesses'),
        isEmpty,
      );
      expect(
        await offline.readCachedSearchPages(query: 'trajet', type: 'journeys'),
        isEmpty,
      );
      final other = HistoryRepository(
        database: db,
        store: ProfileStore(db, 'profile-b'),
        profileId: 'profile-b',
      );
      expect(
        await other.readCachedSearchPages(query: 'trajet', type: 'accesses'),
        isEmpty,
      );
      expect(
        await store.readProjection(
          HistoryRepository.projectionKind,
          resourceKey: offline.resourceKey(offset: 0, limit: 24),
        ),
        isNull,
      );
    },
  );

  test(
    'full History can be prepared incrementally and resumed from SQLite',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final api = _OwnerApi()..totalPages = 2;
      final repo = HistoryRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: SyncEngine(
          api: api,
          store: store,
          database: db,
          profileId: 'profile-a',
        ),
      );
      expect(await repo.prepareHistoryOffline(maxNewPages: 1), isFalse);
      expect(await repo.readPage(offset: 0), isNotNull);
      expect(await repo.readPage(offset: 24), isNull);
      expect(await repo.prepareHistoryOffline(maxNewPages: 1), isTrue);
      expect(await repo.readPage(offset: 24), isNotNull);
      final acquiredRequests = api.calls;
      api.offline = true;
      expect(await repo.prepareHistoryOffline(), isTrue);
      expect(api.calls, acquiredRequests);
      final otherProfile = HistoryRepository(
        database: db,
        store: ProfileStore(db, 'profile-b'),
        profileId: 'profile-b',
      );
      expect(await otherProfile.readPage(offset: 0), isNull);
    },
  );

  testWidgets('known search result and event details remain readable offline', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final repo = HistoryRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
    );
    await store.putProjection(
      kind: HistoryRepository.projectionKind,
      resourceKey: repo.resourceKey(offset: 0, limit: 24),
      schemaVersion: 1,
      payload: {..._page(query: '', type: 'all', title: 'Événement connu')},
    );
    await store.putProjection(
      kind: HistoryRepository.searchProjectionKind,
      resourceKey: HistoryRepository.searchResourceKey(
        query: 'trajet',
        type: 'all',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: _page(query: 'trajet', type: 'all'),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: HistoryScreen(repository: repo, onOpenResource: (_, _) {}),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'trajet');
    await tester.pumpAndSettle();
    expect(find.byTooltip('Rechercher dans Makolo'), findsOneWidget);
    expect(find.text('Accès retrouvé du serveur'), findsOneWidget);
    expect(
      find.textContaining('La recherche porte sur les éléments enregistrés'),
      findsOneWidget,
    );
    await tester.tap(find.text('Accès retrouvé du serveur'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Cet événement est conservé sur votre appareil'),
      findsOneWidget,
    );
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
  });
}
