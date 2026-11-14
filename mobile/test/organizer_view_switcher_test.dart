import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/objective_organizer_data.dart';
import 'package:makolo_mobile/features/continuity/organizer_view_switcher.dart';

void main() {
  testWidgets(
    'Cartes, Liste and Explorateur stay compact, visible and selectable',
    (tester) async {
      var selection = OrganizerMode.cards;
      final picked = <OrganizerMode>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: StatefulBuilder(
                builder: (context, refresh) => OrganizerViewSwitcher(
                  selected: selection,
                  onSelected: (value) {
                    picked.add(value);
                    refresh(() => selection = value);
                  },
                ),
              ),
            ),
          ),
        ),
      );
      final group = find.byKey(const Key('organizer-view-toggle'));
      expect(group, findsOneWidget);
      expect(tester.getSize(group).width, lessThan(145));
      for (final mode in OrganizerMode.values) {
        final button = find.byKey(Key('organizer-view-${mode.name}'));
        expect(button, findsOneWidget);
        expect(tester.getSize(button).width, greaterThanOrEqualTo(44));
        expect(tester.getSize(button).height, greaterThanOrEqualTo(44));
      }

      await tester.tap(find.byTooltip('Vue Liste'));
      await tester.pump();
      await tester.tap(find.byTooltip('Vue Explorateur'));
      await tester.pump();
      expect(picked, [OrganizerMode.list, OrganizerMode.explorer]);
      expect(selection, OrganizerMode.explorer);
      expect(find.byTooltip('Vue Cartes'), findsOneWidget);
    },
  );
}
