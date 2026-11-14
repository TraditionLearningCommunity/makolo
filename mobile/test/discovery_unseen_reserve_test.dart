import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_unseen_reserve.dart';

Map<String, dynamic> candidate(int index) => {
  'identity': {'candidate_key': 'server-$index', 'family': 'activity'},
  'representation': {'title': 'Activité $index'},
  'saved': {'state': 'not_saved'},
};

void main() {
  test('reserve reveals 13 of 20 then respects next five in server order', () {
    final reserve = DiscoveryUnseenReserve();
    final first = List.generate(20, (index) => candidate(index));
    reserve.observe(first);
    final initial = reserve.reveal(
      first.map((row) => DiscoveryUnseenReserve.keyOf(row)!),
      count: 13,
    );
    expect(initial, List.generate(13, (i) => 'server-$i'));
    expect(reserve.unseenCount, 7);
    expect(reserve.isShown('server-12'), isTrue);
    expect(reserve.isShown('server-13'), isFalse);

    final second = List.generate(5, (i) => candidate(i + 20));
    reserve.observe(second);
    final shown = reserve.reveal(
      second.map((row) => DiscoveryUnseenReserve.keyOf(row)!),
      count: 3,
    );
    expect(shown, ['server-20', 'server-21', 'server-22']);
    expect(reserve.unseenCount, 9);
    expect(reserve.isShown('server-23'), isFalse);
    expect(first.last['saved'], {'state': 'not_saved'});
  });

  test('overflow drops oldest unseen only and cannot reintroduce it', () {
    final reserve = DiscoveryUnseenReserve();
    reserve.observe(List.generate(60, candidate));
    expect(reserve.unseenCount, 50);
    expect(reserve.unseenKeys.contains('server-0'), isFalse);
    expect(reserve.unseenKeys.contains('server-9'), isFalse);
    expect(reserve.unseenKeys.contains('server-10'), isTrue);
    reserve.observe([candidate(0), candidate(1)]);
    expect(reserve.unseenCount, 50);
    expect(reserve.pendingFrom(['server-0']), isEmpty);
    reserve.reveal(['server-10'], count: 1);
    reserve.observe(List.generate(10, (i) => candidate(i + 60)));
    expect(reserve.isShown('server-10'), isTrue);
    expect(reserve.unseenCount, 50);
    expect(reserve.unseenKeys.contains('server-11'), isFalse);
  });

  test('offline restore is scoped to Profile, criteria and root revision', () {
    final root = DateTime.utc(2026, 11, 4, 9);
    final reserve = DiscoveryUnseenReserve()
      ..observe([candidate(1), candidate(2)]);
    reserve.reveal(['server-1'], count: 1);
    final data = reserve.toPayload(
      profileId: 'profile-a',
      fieldKey: 'criteria-a',
      rootReceivedAt: root,
    );
    final restored = DiscoveryUnseenReserve.fromPayload(
      data,
      profileId: 'profile-a',
      fieldKey: 'criteria-a',
      rootReceivedAt: root,
    );
    expect(restored, isNotNull);
    expect(restored!.isShown('server-1'), isTrue);
    expect(restored.unseenKeys, {'server-2'});
    expect(
      DiscoveryUnseenReserve.fromPayload(
        data,
        profileId: 'profile-b',
        fieldKey: 'criteria-a',
        rootReceivedAt: root,
      ),
      isNull,
    );
    expect(
      DiscoveryUnseenReserve.fromPayload(
        data,
        profileId: 'profile-a',
        fieldKey: 'criteria-b',
        rootReceivedAt: root,
      ),
      isNull,
    );
    expect(
      DiscoveryUnseenReserve.fromPayload(
        data,
        profileId: 'profile-a',
        fieldKey: 'criteria-a',
        rootReceivedAt: root.add(const Duration(seconds: 1)),
      ),
      isNull,
    );
  });
}
