import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/sync/sync_source.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Map<String, dynamic> _item(String id) => {
  'identity': {
    'family': 'activity',
    'candidate_key': 'activity:$id',
    'resource': {'kind': 'activity', 'id': id},
  },
  'representation': {'kind': 'activity', 'title': 'Formation $id'},
  'saved': {'state': 'not_saved'},
  'capabilities': ['view', 'save'],
};

Map<String, dynamic> _wire(String viewer) => {
  'meta': {
    'projection': 'discovery.items',
    'schema_version': 1,
    'generated_at': '2026-11-02T11:00:00Z',
    'scope': 'personal',
  },
  'data': {
    'surface': 'discover_me',
    'actor': {'type': 'profile', 'id': viewer},
    'viewer': {'type': 'profile', 'id': viewer},
    'count': 1,
    'page': 1,
    'page_size': 24,
    'has_next': false,
    'results': [_item('a')],
    'exploration': <String, dynamic>{},
    'freshness': <String, dynamic>{},
    'selection': {'state': 'ready'},
    'terminal': {'state': 'ok'},
    'continuation': {'state': 'end', 'token': null},
  },
};

MakoloApiClient _api(MockClient client) => MakoloApiClient(
  baseUri: Uri.parse('https://makolo.invalid/'),
  dio: client.dio,
  tokenStore: MemoryTokenStore(
    session: const AuthSession(
      accessToken: 'token',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    ),
  ),
);

void main() {
  test(
    'offline keeps only acquired Profile snapshot, and no new candidates',
    () async {
      var online = true;
      final mock = MockClient((request) async {
        if (!online) throw const SocketException('unreachable');
        return MockResponse(jsonEncode(_wire('profile-a')), 200);
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final a = ProfileStore(database, 'profile-a');
      final b = ProfileStore(database, 'profile-b');
      final api = _api(mock);
      final sync = SyncEngine(
        api: api,
        store: a,
        database: database,
        profileId: 'profile-a',
      );
      final repo = DiscoveryRepository(
        database: database,
        store: a,
        profileId: 'profile-a',
        api: api,
        sync: sync,
      );
      const query = DiscoveryQuery();
      await repo.refreshItems(query);
      expect((await repo.readItems(query))?.payload['count'], 1);
      expect(
        await b.readProjection(
          DiscoveryRepository.itemsProjectionKind,
          resourceKey: query.fingerprint,
        ),
        isNull,
      );
      online = false;
      await repo.refreshItems(query);
      expect((await repo.readItems(query))?.payload['count'], 1);
      final status = await repo.readSource(repo.itemsSource(query));
      expect(status.lastErrorCode, isNotNull);
      expect(status.ownerUnavailable, isFalse);
      expect(await repo.readItems(query.copyWith(text: 'never seen')), isNull);
    },
  );

  test(
    'foreign viewer or mismatched N2 identity is never read from SQLite',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      const query = DiscoveryQuery();
      final api = _api(
        MockClient(
          (request) async => MockResponse(jsonEncode(_wire('profile-a')), 200),
        ),
      );
      final repo = DiscoveryRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        api: api,
      );
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: query.fingerprint,
        schemaVersion: 1,
        payload: Map<String, dynamic>.from(_wire('profile-b')['data'] as Map),
      );
      expect(await repo.readItems(query), isNull);
      await store.putProjection(
        kind: DiscoveryRepository.itemProjectionKind,
        resourceKey: 'activity:requested',
        schemaVersion: 1,
        payload: {'item': _item('someone-else')},
      );
      expect(await repo.readItem('activity', 'requested'), isNull);
    },
  );

  test(
    'owner 403 withdraws all derived Discovery views but not another Profile',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final other = ProfileStore(database, 'profile-b');
      final api = _api(
        MockClient(
          (_) async => MockResponse(
            jsonEncode({
              'error': {
                'code': 'arbitrary_permission_code',
                'message': 'Not allowed',
              },
            }),
            403,
          ),
        ),
      );
      final sync = SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final repo = DiscoveryRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        api: api,
        sync: sync,
      );
      const query = DiscoveryQuery();
      final payload = Map<String, dynamic>.from(
        _wire('profile-a')['data'] as Map,
      );
      for (final kind in [
        DiscoveryRepository.itemsProjectionKind,
        DiscoveryRepository.presentedWindowKind,
        DiscoveryRepository.activityPreviewProjectionKind,
        DiscoveryRepository.itemProjectionKind,
        DiscoveryRepository.watchResultsProjectionKind,
        DiscoveryRepository.mapProjectionKind,
      ]) {
        await store.putProjection(
          kind: kind,
          resourceKey: kind == DiscoveryRepository.itemsProjectionKind
              ? query.fingerprint
              : 'retained',
          schemaVersion: 1,
          payload: payload,
        );
        await other.putProjection(
          kind: kind,
          resourceKey: 'other',
          schemaVersion: 1,
          payload: {'private': 'profile-b'},
        );
      }
      await repo.refreshItems(query);
      expect(
        (await repo.readSource(repo.itemsSource(query))).lastErrorCode,
        'permission_denied',
      );
      for (final kind in [
        DiscoveryRepository.itemsProjectionKind,
        DiscoveryRepository.presentedWindowKind,
        DiscoveryRepository.activityPreviewProjectionKind,
        DiscoveryRepository.itemProjectionKind,
        DiscoveryRepository.watchResultsProjectionKind,
        DiscoveryRepository.mapProjectionKind,
      ]) {
        expect(await store.readProjections(kind), isEmpty);
        expect(
          await other.readProjection(kind, resourceKey: 'other'),
          isNotNull,
        );
      }
      expect(await repo.readItems(query), isNull);
    },
  );

  test(
    'a late 200 cannot rehydrate a field after a newer owner refusal',
    () async {
      final pending = Completer<MockResponse>();
      var calls = 0;
      final mock = MockClient((request) async {
        calls++;
        if (calls == 1) return pending.future;
        return MockResponse(
          jsonEncode({
            'error': {'code': 'no_longer_allowed'},
          }),
          404,
        );
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final engine = SyncEngine(
        api: _api(mock),
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      final source = SyncSourceDefinition.projectionEnvelope(
        sourceKey: 'discovery-watches',
        owner: 'Discovery',
        path: 'api/v1/discovery/watches/',
        projectionKind: DiscoveryRepository.watchesProjectionKind,
      );
      final older = engine.pullSource(source);
      final denied = engine.pullSource(source);
      await expectLater(denied, throwsA(isA<Exception>()));
      pending.complete(
        MockResponse(
          jsonEncode({
            'meta': {
              'projection': 'discovery.watches',
              'schema_version': 1,
              'generated_at': '2026-11-02T11:00:00Z',
            },
            'data': {'results': <Object>[]},
          }),
          200,
        ),
      );
      await older;
      expect(await store.readProjection('discovery.watches'), isNull);
    },
  );

  test(
    'rotation preserves the active page and never evicts another Profile',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final a = ProfileStore(database, 'profile-a');
      final b = ProfileStore(database, 'profile-b');
      for (var i = 0; i < 7; i++) {
        await a.putProjection(
          kind: 'discovery.activity-preview',
          resourceKey: 'item-$i',
          schemaVersion: 1,
          payload: {'id': i},
          receivedAt: DateTime.utc(2026, 11, 1, 0, 0, i),
        );
      }
      await b.putProjection(
        kind: 'discovery.activity-preview',
        resourceKey: 'item-0',
        schemaVersion: 1,
        payload: {'id': 'b'},
      );
      await a.pruneProjectionsOfKind(
        'discovery.activity-preview',
        retain: 2,
        protectResourceKeys: {'item-0'},
      );
      final kept = await a.readProjections('discovery.activity-preview');
      expect(kept.map((v) => v.resourceKey).toSet(), {
        'item-0',
        'item-5',
        'item-6',
      });
      expect(
        (await b.readProjection(
          'discovery.activity-preview',
          resourceKey: 'item-0',
        ))?.payload['id'],
        'b',
      );
    },
  );
}
