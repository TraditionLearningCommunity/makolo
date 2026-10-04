import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:makolo_mobile/presentation/humanization.dart';

void main() {
  setUpAll(() async {
    await initializeDateFormatting('fr');
  });

  test('technical status values become contextual human labels', () {
    expect(MakoloHumanization.humanStatus('scheduled'), 'Prévu');
    expect(MakoloHumanization.humanStatus('available'), 'Disponible');
    expect(MakoloHumanization.humanStatus('action_required'), 'À faire');
    expect(MakoloHumanization.humanStatus('unknown'), isNull);
    expect(MakoloHumanization.presentationLabel('custom_backend_state'), isNull);
    expect(MakoloHumanization.presentationLabel('En cours de validation'), 'En cours de validation');
  });

  test('timezone identifiers are reduced to human place labels', () {
    expect(MakoloHumanization.humanTimezone('Africa/Lubumbashi'), 'Lubumbashi');
    expect(MakoloHumanization.humanTimezone('UTC'), isNull);
  });

  test('dates use human relative days and never expose ISO input', () {
    final now = DateTime(2026, 10, 4, 12);
    final today = DateTime(2026, 10, 4, 9);
    final tomorrow = DateTime(2026, 10, 5, 9);

    expect(MakoloHumanization.formatDay(today, now: now), 'Aujourd’hui');
    expect(MakoloHumanization.formatDay(tomorrow, now: now), 'Demain');
    expect(
      MakoloHumanization.formatDateTime(today, now: now),
      contains('09:00'),
    );
    expect(
      MakoloHumanization.formatDateTime(today, now: now),
      isNot(contains('2026-10-04T')),
    );
  });

  test('duration and percent formatting stay locale-aware', () {
    expect(
      MakoloHumanization.formatDuration(const Duration(minutes: 90)),
      '1 heure 30 min',
    );
    expect(MakoloHumanization.formatPercentFraction(0.33), contains('33'));
  });
}
