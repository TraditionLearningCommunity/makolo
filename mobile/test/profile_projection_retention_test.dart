import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';

void main() {
  test(
    'raw Discovery cursor views remain available alongside owner roots',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      await store.putProjection(
        kind: 'personal.me',
        schemaVersion: 1,
        payload: {'full': true, 'count': 25},
      );
      await store.putProjection(
        kind: 'personal.ongoing',
        schemaVersion: 1,
        payload: {'active': true},
      );
      await store.putProjection(
        kind: 'personal.now',
        schemaVersion: 1,
        payload: {'current': true},
      );

      for (var i = 0; i < 13; i++) {
        await store.putProjection(
          kind: 'discovery.item',
          resourceKey: 'item-$i',
          schemaVersion: 1,
          payload: {'id': 'item-$i'},
          receivedAt: DateTime.utc(2026, 10, 1).add(Duration(minutes: i)),
        );
      }
      expect((await store.readProjections('discovery.item')).length, 13);
      expect(
        await store.readProjection('discovery.item', resourceKey: 'item-0'),
        isNotNull,
      );
      expect(
        await store.readProjection('discovery.item', resourceKey: 'item-12'),
        isNotNull,
      );
      expect((await store.readProjection('personal.me'))?.payload['count'], 25);
      expect(await store.readProjection('personal.ongoing'), isNotNull);
      expect(await store.readProjection('personal.now'), isNotNull);
    },
  );

  test('Discovery rotation is isolated across Profiles', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final a = ProfileStore(database, 'profile-a');
    final b = ProfileStore(database, 'profile-b');
    await b.putProjection(
      kind: 'discovery.item',
      resourceKey: 'other',
      schemaVersion: 1,
      payload: {'id': 'other'},
    );
    for (var i = 0; i < 13; i++) {
      await a.putProjection(
        kind: 'discovery.item',
        resourceKey: 'mine-$i',
        schemaVersion: 1,
        payload: {'id': i},
      );
    }
    expect((await a.readProjections('discovery.item')).length, 13);
    expect((await b.readProjections('discovery.item')).length, 1);
    expect(
      await b.readProjection('discovery.item', resourceKey: 'other'),
      isNotNull,
    );
  });
}
