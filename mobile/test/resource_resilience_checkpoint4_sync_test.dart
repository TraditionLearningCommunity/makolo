import 'dart:async';
import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/features/resources/trust_resource_repository.dart';
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
    'page': {
      'offset': 0,
      'limit': 24,
      'count': ids.length,
      'has_more': false,
    },
  },
  'proofs': {'count': 0, 'items': <Object>[]},
  'credentials': {'count': 0, 'items': <Object>[]},
};

void main() {
  test(
    'PersonalAsset detail denial redacts every acquired view and stale pulls cannot resurrect it',
    () async {
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
              'meta': {
                'projection': 'personal.me',
                'schema_version': 1,
              },
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
        resourceKey: repository.collectionResourceKey(
          query: '',
          offset: 0,
        ),
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

      await repository.refreshDetail(deniedId);

      final page = await repository.readCollectionPage(query: '', offset: 0);
      final pageItems =
          ((page!.payload['documents'] as Map)['items'] as List)
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
      final refreshed = await repository.readCollectionPage(
        query: '',
        offset: 0,
      );
      final refreshedItems =
          ((refreshed!.payload['documents'] as Map)['items'] as List)
              .cast<Map>();
      expect(refreshedItems.map((row) => row['id']), [keptId]);

      await sync.refreshPersonalMe();
      final refreshedMe = await store.readProjection('personal.me');
      final refreshedMeItems =
          ((((refreshedMe!.payload['resources'] as Map)['documents']
                      as Map)['items'])
                  as List)
              .cast<Map>();
      expect(refreshedMeItems.map((row) => row['id']), [keptId]);
    },
  );

  test(
    'in-flight collection started before a detail denial cannot restore the denied resource',
    () async {
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

      final collection = repository.refreshCollectionPage(
        query: '',
        offset: 0,
      );
      await entered.future;
      await repository.refreshDetail(deniedId);
      release.complete();
      await collection;

      expect(
        await repository.readCollectionPage(query: '', offset: 0),
        isNull,
      );
    },
  );

  test(
    'Trust detail denial redacts acquired Proof rows and stale owner pages stay filtered',
    () async {
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
              'meta': {
                'projection': 'personal.proofs',
                'schema_version': 1,
              },
              'data': {
                'query': '',
                'status': 'all',
                'sort': 'recent',
                'count': 2,
                'items': [
                  {'id': deniedId, 'proof_type_label': 'Denied'},
                  {'id': keptId, 'proof_type_label': 'Kept'},
                ],
                'page': {
                  'offset': 0,
                  'limit': 24,
                  'count': 2,
                  'has_more': false,
                },
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
          'page': {
            'offset': 0,
            'limit': 24,
            'count': 2,
            'has_more': false,
          },
        },
      );

      await repository.refreshDetail(
        TrustResourceFamily.proofs,
        deniedId,
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
      final ids = (page!.payload['items'] as List)
          .cast<Map>()
          .map((row) => row['id']);
      expect(ids, [keptId]);
    },
  );

  test('fresh resource detail is reused and stale detail is reacquired', () async {
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
  });
}
