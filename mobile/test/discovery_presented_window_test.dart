import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _OfflineApi implements MakoloApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) =>
      super.noSuchMethod(invocation);
}

Map<String, dynamic> _item(int index) => {
  'identity': {
    'family': 'activity',
    'candidate_key': 'activity:item-$index',
    'resource': {'kind': 'activity', 'id': 'item-$index'},
  },
  'representation': {
    'kind': 'event',
    'title': 'Possibilité $index',
    'summary': 'Information reçue du serveur',
  },
  'capabilities': ['view'],
  'saved': {'state': 'not_saved'},
  'links': <String, String>{},
};

Map<String, dynamic> _page(int page, int start, String? next) => {
  'page': page,
  'page_size': 24,
  'count': 72,
  'has_next': next != null,
  'results': List.generate(24, (index) => _item(start + index)),
  'continuation': {
    'state': next == null ? 'end' : 'more',
    'token': next,
  },
};

void main() {
  test('Discovery rotates old raw pages while preserving latest 50 facts and cursor',
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
    const page1 = DiscoveryQuery();
    final page2 = page1.copyWith(page: 2, continuation: 'opaque-1');
    final page3 = page1.copyWith(page: 3, continuation: 'opaque-2');

    Future<void> seed(DiscoveryQuery query, Map<String, dynamic> payload) =>
        store.putProjection(
          kind: DiscoveryRepository.itemsProjectionKind,
          resourceKey: query.fingerprint,
          schemaVersion: 1,
          payload: payload,
        );

    await seed(page1, _page(1, 1, 'opaque-1'));
    await seed(page2, _page(2, 25, 'opaque-2'));
    await repository.retainPresentedWindow(page2);
    await seed(page3, _page(3, 49, null));
    await repository.retainPresentedWindow(page3);

    expect(
      await store.readProjection(
        DiscoveryRepository.itemsProjectionKind,
        resourceKey: page2.fingerprint,
      ),
      isNull,
    );
    expect(
      await store.readProjection(
        DiscoveryRepository.itemsProjectionKind,
        resourceKey: page1.fingerprint,
      ),
      isNotNull,
    );
    final last = await repository.readItems(page3);
    final items = const DiscoverySelector().collection(last).items;
    expect(items.length, DiscoveryRepository.maxPresentedWindowItems);
    expect(items.first.id, 'item-23');
    expect(items.last.id, 'item-72');
  });
}
