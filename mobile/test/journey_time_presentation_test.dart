import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/journey/journey_time_presentation.dart';

void main() {
  group('Journey day is a civil date, not a Journey status', () {
    const date = '2026-12-11';

    test('supports distant days, the day itself and unlimited past days', () {
      const zone = 'Africa/Lubumbashi';
      final cases = <(DateTime, String)>[
        (DateTime.utc(2026, 4, 10, 12), 'Jour −245'),
        (DateTime.utc(2026, 11, 25, 12), 'Jour −16'),
        (DateTime.utc(2026, 12, 9, 12), 'Jour −2'),
        (DateTime.utc(2026, 12, 11, 12), 'Jour J'),
        (DateTime.utc(2026, 12, 13, 12), 'Jour J +2'),
        (DateTime.utc(2027, 6, 5, 12), 'Jour J +176'),
      ];
      for (final item in cases) {
        expect(
          JourneyDayPresentation.badge(
            date,
            item.$1,
            timezoneName: zone,
          ),
          item.$2,
        );
      }
    });

    test('uses Occurrence timezone, not the phone or UTC day boundary', () {
      final now = DateTime.utc(2026, 12, 10, 22, 30);
      expect(
        JourneyDayPresentation.badge(
          date,
          now,
          timezoneName: 'Africa/Lubumbashi',
        ),
        'Jour J',
      );
      expect(
        JourneyDayPresentation.badge(
          date,
          now,
          timezoneName: 'America/New_York',
        ),
        'Jour −1',
      );
      final untilMidnight = JourneyDayPresentation.nextMidnightDelay(
        now,
        timezoneName: 'Africa/Lubumbashi',
      );
      expect(untilMidnight.inMinutes, 1410);
    });

    test('unknown or malformed owner dates never create a false marker', () {
      final now = DateTime.utc(2026, 11, 10);
      expect(JourneyDayPresentation.badge(null, now), isNull);
      expect(JourneyDayPresentation.badge('2026-02-30', now), isNull);
      expect(JourneyDayPresentation.badge('2026-12-11T09:00', now), isNull);
      expect(
        JourneyDayPresentation.badge(
          date,
          now,
          timezoneName: 'Unknown/Timezone',
        ),
        isNull,
      );
    });

    test('formats clock and place without technical timezone or duplicates', () {
      expect(JourneyDayPresentation.clock('09:00:00'), '09h00');
      expect(JourneyDayPresentation.clock('23:59'), '23h59');
      expect(JourneyDayPresentation.clock('25:60:00'), isNull);
      expect(
        JourneyDayPresentation.place(
          name: 'Lubumbashi',
          locality: 'Lubumbashi',
        ),
        'Lubumbashi',
      );
      expect(
        JourneyDayPresentation.additionalPlace(
          name: 'Lubumbashi',
          locality: 'Lubumbashi',
        ),
        isNull,
      );
      expect(
        JourneyDayPresentation.additionalPlace(
          name: 'Centre de conférence',
          locality: 'Lubumbashi',
          address: 'Avenue centrale',
        ),
        'Avenue centrale · Lubumbashi',
      );
    });
  });
}
