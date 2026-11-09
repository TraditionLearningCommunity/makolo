import 'dart:async';
import 'dart:convert';

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/features/resources/trust_resource_repository.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

MakoloApiClient _api(
  Future<MockResponse> Function(MockRequest request) handler,
) => MakoloApiClient(
  baseUri: Uri.parse('https://makolo.invalid/'),
  tokenStore: MemoryTokenStore(
    session: const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    ),
  ),
  dio: MockClient(handler).dio,
);

Map<String, dynamic> _documentsPayload(List<String> ids) => {
  'documents': {
    'query': '',
    'view': 'current',
    'sort': 'recent',
    'filters': {'kind': '', 'sensitivity': ''},
    'count': ids.length,
    'items': [
      for (final id in ids)
        {
          'id': id,
          'title': 'Document $id',
          'asset_kind_label': 'Document',
          'sensitivity': 'normal',
        },
    ],
    'page': {'offset': 0, 'limit': 24, 'count': ids.length, 'has_more': false},
  },
  'proofs': {'count': 0, 'items': <Object>[]},
  'credentials': {'count': 0, 'items': <Object>[]},
};

void main() {
  test('PersonalAsset detail denial redacts every acquired view and stale pulls cannot resurrect it', () async {
    const deniedId = 'asset-denied';
    const keptId = 'asset-kept';
    var staleCollection = false;
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final api = _api((request) async {
      final path = request.url.path;
      if (path == '/api/v1/me/resources/$deniedId/') {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied', 'message': 'Denied'},
          }),
          403,
        );
      }
      if (path == '/api/v1/me/resources/') {
        expect(staleCollection, isTrue);
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': ResourceRepository.collectionProjectionKind,
              'schema_version': 1,
            },
            'data': _documentsPayload([deniedId, keptId]),
          }),
          200,
        );
      }
      if (path == '/api/v1/me/') {
        return MockResponse(
          jsonEncode({
            'meta': {'projection': 'personal.me', 'schema_version': 1},
            'data': {
              'actor': {'id': 'profile-a'},
              'resources': _documentsPayload([deniedId, keptId]),
            },
          }),
          200,
        );
      }
      throw StateError('Unexpected path $path');
    });
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      store: store,
      database: db,
      profileId: 'profile-a',
    );
    final repository = ResourceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
      api: api,
    );

    await store.putProjection(
      kind: ResourceRepository.collectionProjectionKind,
      resourceKey: repository.collectionResourceKey(query: '', offset: 0),
      schemaVersion: 1,
      payload: _documentsPayload([deniedId, keptId]),
    );
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: 1,
      payload: {
        'resources': _documentsPayload([deniedId, keptId]),
      },
    );

    await expectLater(
      repository.refreshDetail(deniedId),
      throwsA(isA<MakoloApiError>()),
    );

    final page = await repository.readCollectionPage(query: '', offset: 0);
    final pageItems = ((page!.payload['documents'] as Map)['items'] as List)
        .cast<Map>();
    expect(pageItems.map((row) => row['id']), [keptId]);
    final me = await store.readProjection('personal.me');
    final meItems =
        ((((me!.payload['resources'] as Map)['documents'] as Map)['items'])
                as List)
            .cast<Map>();
    expect(meItems.map((row) => row['id']), [keptId]);

    staleCollection = true;
    await repository.refreshCollectionPage(query: '', offset: 0);
    final refreshed = await repository.readCollectionPage(query: '', offset: 0);
    final refreshedItems =
        ((refreshed!.payload['documents'] as Map)['items'] as List).cast<Map>();
    expect(refreshedItems.map((row) => row['id']), [keptId]);

    await sync.refreshPersonalMe();
    final refreshedMe = await store.readProjection('personal.me');
    final refreshedMeItems =
        ((((refreshedMe!.payload['resources'] as Map)['documents']
                    as Map)['items'])
                as List)
            .cast<Map>();
    expect(refreshedMeItems.map((row) => row['id']), [keptId]);
  });

  test('in-flight collection started before a detail denial cannot restore the denied resource', () async {
    const deniedId = 'asset-race';
    final entered = Completer<void>();
    final release = Completer<void>();
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final api = _api((request) async {
      if (request.url.path == '/api/v1/me/resources/' &&
          request.url.queryParameters.containsKey('limit')) {
        if (!entered.isCompleted) entered.complete();
        await release.future;
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': ResourceRepository.collectionProjectionKind,
              'schema_version': 1,
            },
            'data': _documentsPayload([deniedId]),
          }),
          200,
        );
      }
      if (request.url.path == '/api/v1/me/resources/$deniedId/') {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'not_found', 'message': 'Gone'},
          }),
          404,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      store: store,
      database: db,
      profileId: 'profile-a',
    );
    final repository = ResourceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
      api: api,
    );

    final collection = repository.refreshCollectionPage(query: '', offset: 0);
    await entered.future;
    await expectLater(
      repository.refreshDetail(deniedId),
      throwsA(isA<MakoloApiError>()),
    );
    release.complete();
    await collection;

    expect(await repository.readCollectionPage(query: '', offset: 0), isNull);
  });

  test('Trust detail denial redacts acquired Proof rows and stale owner pages stay filtered', () async {
    const deniedId = 'proof-denied';
    const keptId = 'proof-kept';
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final api = _api((request) async {
      if (request.url.path == '/api/v1/me/proofs/$deniedId/') {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied', 'message': 'Denied'},
          }),
          403,
        );
      }
      if (request.url.path == '/api/v1/me/proofs/') {
        return MockResponse(
          jsonEncode({
            'meta': {'projection': 'personal.proofs', 'schema_version': 1},
            'data': {
              'query': '',
              'status': 'all',
              'sort': 'recent',
              'count': 2,
              'items': [
                {'id': deniedId, 'proof_type_label': 'Denied'},
                {'id': keptId, 'proof_type_label': 'Kept'},
              ],
              'page': {'offset': 0, 'limit': 24, 'count': 2, 'has_more': false},
            },
          }),
          200,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      store: store,
      database: db,
      profileId: 'profile-a',
    );
    final repository = TrustResourceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
      api: api,
    );
    final resourceKey = repository.collectionResourceKey(
      family: TrustResourceFamily.proofs,
      query: '',
      status: 'all',
      type: '',
      sort: 'recent',
      offset: 0,
    );
    await store.putProjection(
      kind: 'personal.proofs',
      resourceKey: resourceKey,
      schemaVersion: 1,
      payload: {
        'query': '',
        'status': 'all',
        'sort': 'recent',
        'count': 2,
        'items': [
          {'id': deniedId, 'proof_type_label': 'Denied'},
          {'id': keptId, 'proof_type_label': 'Kept'},
        ],
        'page': {'offset': 0, 'limit': 24, 'count': 2, 'has_more': false},
      },
    );

    await expectLater(
      repository.refreshDetail(TrustResourceFamily.proofs, deniedId),
      throwsA(isA<MakoloApiError>()),
    );
    await repository.refreshCollectionPage(
      family: TrustResourceFamily.proofs,
      query: '',
      offset: 0,
    );

    final page = await repository.readCollectionPage(
      family: TrustResourceFamily.proofs,
      query: '',
      offset: 0,
    );
    final ids = (page!.payload['items'] as List).cast<Map>().map(
      (row) => row['id'],
    );
    expect(ids, [keptId]);
  });

  test(
    'fresh resource detail is reused and stale detail is reacquired',
    () async {
      var calls = 0;
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final api = _api((request) async {
        calls++;
        return MockResponse(
          jsonEncode({
            'meta': {
              'projection': ResourceRepository.detailProjectionKind,
              'schema_version': 1,
            },
            'data': {'id': 'asset-fresh', 'title': 'Owner refresh'},
          }),
          200,
        );
      });
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        store: store,
        database: db,
        profileId: 'profile-a',
      );
      final repository = ResourceRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: sync,
        api: api,
      );

      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-fresh',
        schemaVersion: 1,
        payload: {'id': 'asset-fresh', 'title': 'Local'},
        receivedAt: DateTime.now().toUtc(),
      );
      await repository.ensureDetail('asset-fresh');
      expect(calls, 0);

      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-fresh',
        schemaVersion: 1,
        payload: {'id': 'asset-fresh', 'title': 'Old local'},
        receivedAt: DateTime.now().toUtc().subtract(const Duration(hours: 3)),
      );
      await repository.ensureDetail('asset-fresh');
      expect(calls, 1);
      expect(
        (await repository.readDetail('asset-fresh'))?.payload['title'],
        'Owner refresh',
      );
    },
  );

  test('collection denial withdraws every cached page but keeps independent resource details', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final api = _api(
      (request) async => MockResponse(
        jsonEncode({
          'error': {'code': 'permission_denied', 'message': 'Denied'},
        }),
        403,
      ),
    );
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      store: store,
      database: db,
      profileId: 'profile-a',
    );
    final repository = ResourceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
      api: api,
    );

    for (final offset in [0, 24]) {
      await store.putProjection(
        kind: ResourceRepository.collectionProjectionKind,
        resourceKey: repository.collectionResourceKey(
          query: '',
          offset: offset,
        ),
        schemaVersion: 1,
        payload: _documentsPayload(['asset-$offset']),
      );
    }
    await store.putProjection(
      kind: ResourceRepository.detailProjectionKind,
      resourceKey: 'asset-independent',
      schemaVersion: 1,
      payload: {'id': 'asset-independent', 'title': 'Détail indépendant'},
    );

    await repository.refreshCollectionPage(query: '', offset: 0);

    expect(
      await store.readProjections(ResourceRepository.collectionProjectionKind),
      isEmpty,
    );
    expect(await repository.readDetail('asset-independent'), isNotNull);
  });

  test(
    'generic invalidation preserves a confirmed resource owner tombstone',
    () async {
      const deniedId = 'asset-tombstone';
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final api = _api(
        (request) async => MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied', 'message': 'Denied'},
          }),
          403,
        ),
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        store: store,
        database: db,
        profileId: 'profile-a',
      );
      final repository = ResourceRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: sync,
        api: api,
      );
      final source = repository.detailSourceFor(deniedId);

      await expectLater(
        repository.refreshDetail(deniedId),
        throwsA(isA<MakoloApiError>()),
      );
      await sync.invalidate(source);

      final row =
          await (db.select(db.syncSources)..where(
                (item) =>
                    item.profileId.equals('profile-a') &
                    item.sourceKey.equals(source.sourceKey),
              ))
              .getSingle();
      expect(row.invalidated, isTrue);
      expect(row.lastErrorCode, 'permission_denied');
    },
  );

  test('Credential denial cannot survive in titles or Moi previews', () async {
    const deniedId = 'credential-denied';
    const keptId = 'credential-kept';
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final api = _api((request) async {
      if (request.url.path == '/api/v1/me/titles/$deniedId/') {
        return MockResponse(
          jsonEncode({
            'error': {'code': 'not_found', 'message': 'Gone'},
          }),
          404,
        );
      }
      throw StateError('Unexpected request ${request.url}');
    });
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      store: store,
      database: db,
      profileId: 'profile-a',
    );
    final repository = TrustResourceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
      api: api,
    );

    final titlesKey = repository.collectionResourceKey(
      family: TrustResourceFamily.titles,
      query: '',
      status: 'all',
      type: '',
      sort: 'recent',
      offset: 0,
    );
    await store.putProjection(
      kind: 'personal.titles',
      resourceKey: titlesKey,
      schemaVersion: 1,
      payload: {
        'items': [
          {'id': deniedId, 'title': 'Ancien titre'},
          {'id': keptId, 'title': 'Titre conservé'},
        ],
        'count': 2,
        'page': {'offset': 0, 'limit': 24, 'count': 2, 'has_more': false},
      },
    );
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: 1,
      payload: {
        'resources': {
          'documents': {'items': <Object>[], 'count': 0},
          'proofs': {'items': <Object>[], 'count': 0},
          'credentials': {
            'items': [
              {'id': deniedId, 'title': 'Ancien titre'},
              {'id': keptId, 'title': 'Titre conservé'},
            ],
            'count': 2,
          },
        },
      },
    );

    await expectLater(
      repository.refreshDetail(TrustResourceFamily.titles, deniedId),
      throwsA(isA<MakoloApiError>()),
    );

    final titles = await store.readProjection(
      'personal.titles',
      resourceKey: titlesKey,
    );
    expect(
      (titles!.payload['items'] as List).cast<Map>().map((row) => row['id']),
      [keptId],
    );
    final me = await store.readProjection('personal.me');
    final credentials =
        (((me!.payload['resources'] as Map)['credentials'] as Map)['items'])
            as List;
    expect(credentials.cast<Map>().map((row) => row['id']), [keptId]);
  });

  test('fresh Trust detail is reused without a redundant owner GET', () async {
    var calls = 0;
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final api = _api((request) async {
      calls++;
      return MockResponse('{}', 500);
    });
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      store: store,
      database: db,
      profileId: 'profile-a',
    );
    final repository = TrustResourceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
      api: api,
    );
    await store.putProjection(
      kind: TrustResourceFamily.proofs.detailProjection,
      resourceKey: 'proof-fresh',
      schemaVersion: 1,
      payload: {'id': 'proof-fresh', 'proof_type_label': 'Journey accomplie'},
      receivedAt: DateTime.now().toUtc(),
    );

    await repository.ensureDetail(TrustResourceFamily.proofs, 'proof-fresh');
    expect(calls, 0);
  });
}
