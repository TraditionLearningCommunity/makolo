import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_unseen_reserve.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _OfflineApi implements MakoloApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> candidate(String key) => {
  'identity': {
    'family': 'activity',
    'candidate_key': key,
    'resource': {'kind': 'activity', 'id': key},
  },
  'representation': {'kind': 'event', 'title': 'Possibilité $key'},
  'capabilities': ['view'],
  'saved': {'state': 'not_saved'},
  'links': <String, String>{},
};

Map<String, dynamic> serverField() => {
  'viewer': {'id': 'profile-a'},
  'page': 1,
  'page_size': 24,
  'count': 2,
  'has_next': false,
  'results': [candidate('a'), candidate('b')],
  'continuation': {'state': 'end'},
};

void main() {
  test(
    'unseen reserve persists per Profile and cannot rebind to a new root',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final repository = DiscoveryRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        api: _OfflineApi(),
      );
      const query = DiscoveryQuery();
      final first = DateTime.utc(2026, 11, 4, 9);
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: query.fingerprint,
        schemaVersion: 1,
        payload: serverField(),
        receivedAt: first,
      );
      final reserve = DiscoveryUnseenReserve(rootReceivedAt: first)
        ..observe([candidate('a'), candidate('b')]);
      reserve.reveal(['a'], count: 1);
      await repository.saveUnseenReserve(query, reserve);
      final restored = await repository.readUnseenReserve(query);
      expect(restored?.shownKeys, {'a'});
      expect(restored?.unseenKeys, {'b'});

      final other = DiscoveryRepository(
        database: db,
        store: ProfileStore(db, 'profile-b'),
        profileId: 'profile-b',
        api: _OfflineApi(),
      );
      expect(await other.readUnseenReserve(query), isNull);
      final updated = first.add(const Duration(seconds: 1));
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: query.fingerprint,
        schemaVersion: 1,
        payload: serverField(),
        receivedAt: updated,
      );
      expect(await repository.readUnseenReserve(query), isNull);
      await repository.saveUnseenReserve(query, reserve);
      expect(await repository.readUnseenReserve(query), isNull);

      await db
          .into(db.syncSources)
          .insert(
            SyncSourcesCompanion.insert(
              profileId: 'profile-a',
              sourceKey: repository.itemsSource(query).sourceKey,
              route: 'api/v1/discovery/items/',
              invalidated: const Value(true),
              lastErrorCode: const Value('permission_denied'),
            ),
          );
      expect(await repository.readUnseenReserve(query), isNull);
    },
  );
}
