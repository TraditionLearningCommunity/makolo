import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_screens.dart';

void main() {
  StoredProjection position(Map<String, dynamic> payload) => StoredProjection(
    kind: 'discovery.presentation-position',
    schemaVersion: 1,
    payload: payload,
    receivedAt: DateTime.utc(2026, 10, 30),
  );

  test('a received Discovery position restores the same opaque cursor', () {
    final restored = retainedDiscoveryPosition(
      position({'page': 2, 'continuation': 'signed-server-token'}),
    );
    expect(restored?.page, 2);
    expect(restored?.continuation, 'signed-server-token');
  });

  test('missing or malformed cursors cannot become new Discovery data', () {
    expect(retainedDiscoveryPosition(null), isNull);
    expect(retainedDiscoveryPosition(
      position({'page': 1, 'continuation': 'old'}),
    ), isNull);
    expect(retainedDiscoveryPosition(
      position({'page': 3, 'continuation': ''}),
    ), isNull);
    expect(retainedDiscoveryPosition(
      position({'page': 'not-a-page', 'continuation': 'x'}),
    ), isNull);
  });
}
