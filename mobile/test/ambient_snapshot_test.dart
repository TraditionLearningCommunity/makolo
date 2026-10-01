import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/ambient/ambient_snapshot.dart';

void main() {
  test('ambient snapshot exposes only the minimal presentation contract', () {
    final snapshot = AmbientSnapshot(
      kind: 'next_action',
      title: 'Préparer le départ',
      subtitle: 'Une étape utile',
      status: 'ready',
      timeLabel: '08:00',
      placeLabel: 'Lubumbashi',
      deepLink: 'makolo://journeys/journey-1',
      updatedAt: DateTime.utc(2026, 10, 1, 8),
    );

    expect(snapshot.toMap(), {
      'kind': 'next_action',
      'title': 'Préparer le départ',
      'subtitle': 'Une étape utile',
      'status': 'ready',
      'time': '08:00',
      'place': 'Lubumbashi',
      'deep_link': 'makolo://journeys/journey-1',
      'updated_at': '2026-10-01T08:00:00.000Z',
    });
  });
}
