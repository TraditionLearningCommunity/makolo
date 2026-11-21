import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Map<String, dynamic> _access(String id) => {
  'identity': {'kind': 'access', 'id': id},
  'relationship': 'beneficiary',
  'capabilities': ['present_credential'],
  'links': {'credential': '/api/v1/me/accesses/$id/credential/'},
};

Map<String, dynamic> _collection(List<String> ids) => {
  'meta': {
    'projection': AccessRepository.collectionProjectionKind,
    'schema_version': 1,
  },
  'data': {
    'items': ids.map(_access).toList(),
    'page': {'offset': 0, 'limit': 24, 'has_more': false},
  },
};

void main() {
  test(
    'detail 403 redacts only its Access, even in a later list response',
    () async {
      var delayed = false;
      final started = Completer<void>();
      final response = Completer<MockResponse>();
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
        dio: MockClient((request) async {
          if (request.url.path == '/api/v1/me/accesses/a/') {
            return MockResponse(
              jsonEncode({
                'error': {
                  'code': 'server_unavailable',
                  'message': 'Retry later',
                },
              }),
              503,
            );
          }
          if (request.url.path == '/api/v1/me/accesses/' && delayed) {
            if (!started.isCompleted) started.complete();
            return response.future;
          }
          return MockResponse(jsonEncode(_collection(['a', 'b'])), 200);
        }).dio,
      );
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      addTearDown(api.close);
      final store = ProfileStore(db, 'profile-a');
      final engine = SyncEngine(
        api: api,
        database: db,
        store: store,
        profileId: 'profile-a',
      );
      final repository = AccessRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: engine,
        api: api,
      );
      final list = repository.collectionSourceFor(
        relationship: 'beneficiary',
        offset: 0,
      );

      await engine.pullSource(list);
      expect(
        (await repository.readCollectionPage(
          relationship: 'beneficiary',
          offset: 0,
        ))?.payload['items'],
        hasLength(2),
      );

      delayed = true;
      final inFlight = engine.pullSource(list);
      await started.future;
      await engine.revoke(repository.sourceFor('a'));
      response.complete(MockResponse(jsonEncode(_collection(['a', 'b'])), 200));
      await inFlight;
      var page = await repository.readCollectionPage(
        relationship: 'beneficiary',
        offset: 0,
      );
      expect((page?.payload['items'] as List), hasLength(1));
      expect(
        ((page?.payload['items'] as List).single as Map)['identity']['id'],
        'b',
      );

      delayed = false;
      await engine.pullSource(list);
      page = await repository.readCollectionPage(
        relationship: 'beneficiary',
        offset: 0,
      );
      expect(
        (page?.payload['items'] as List),
        hasLength(1),
        reason: 'A successful collection is not keyed Access reauthorization',
      );

      await engine.invalidate(repository.sourceFor('a'));
      await expectLater(
        engine.pullSource(repository.sourceFor('a')),
        throwsA(isA<MakoloApiError>()),
      );
      final denied = await repository.readSource('a');
      expect(denied.invalidated, isTrue);
      expect(denied.lastErrorCode, 'permission_denied');
      await engine.pullSource(list);
      expect(
        ((await repository.readCollectionPage(
              relationship: 'beneficiary',
              offset: 0,
            ))!.payload['items']
            as List),
        hasLength(1),
        reason: 'Soft invalidation cannot clear explicit Access denial',
      );
    },
  );

  test(
    'buyer collection refusal never revokes independent beneficiary pages',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'access',
            refreshToken: 'refresh',
            profileId: 'profile-a',
          ),
        ),
        dio: MockClient((_) async => const MockResponse('{}', 200)).dio,
      );
      addTearDown(api.close);
      final engine = SyncEngine(
        api: api,
        store: store,
        database: db,
        profileId: 'profile-a',
      );
      final access = AccessRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: engine,
      );
      for (final relationship in ['beneficiary', 'purchased_for_other']) {
        await store.putProjection(
          kind: AccessRepository.collectionProjectionKind,
          resourceKey: access.collectionResourceKey(
            relationship: relationship,
            offset: 0,
          ),
          schemaVersion: 1,
          payload: {
            'items': [_access('b')],
            'page': {},
          },
        );
      }
      await engine.revoke(
        access.collectionSourceFor(
          relationship: 'purchased_for_other',
          offset: 0,
        ),
      );
      expect(
        await access.readCollectionPage(
          relationship: 'purchased_for_other',
          offset: 0,
        ),
        isNull,
      );
      expect(
        await access.readCollectionPage(relationship: 'beneficiary', offset: 0),
        isNotNull,
      );

      await engine.revoke(
        access.collectionSourceFor(relationship: 'beneficiary', offset: 0),
      );
      expect(
        await access.readCollectionPage(relationship: 'beneficiary', offset: 0),
        isNull,
      );
      expect(
        await access.readCollectionPage(
          relationship: 'purchased_for_other',
          offset: 0,
        ),
        isNull,
      );
    },
  );
}
