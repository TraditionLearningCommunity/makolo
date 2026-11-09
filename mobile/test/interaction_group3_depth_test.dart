import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/features/space/space_work_g3_depth.dart';
import 'package:makolo_mobile/features/space/space_work_g1_realizations.dart';

void main() {
  testWidgets(
    'Group 3 offer edit action is rendered only with owner capability',
    (tester) async {
      Future<void> render(bool allowed) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                SpaceWorkG3Depth(
                  slug: 'boutique',
                  ownerId: 'offer-42',
                  payload: {
                    'kind': 'offer',
                    'facts': {
                      'currency': 'USD',
                      'unit_price': '20.00',
                      'payment_mode': 'upfront',
                      'currently_available': true,
                      'can_manage_offer': allowed,
                    },
                  },
                  onPageChange: (_) {},
                  onSecondaryPageChange: (_) {},
                ),
              ],
            ),
          ),
        ),
      );

      await render(false);
      expect(find.text('Modifier l’offre'), findsNothing);
      await render(true);
      final action = find.widgetWithText(
        MakoloActionButton,
        'Modifier l’offre',
      );
      expect(action, findsOneWidget);
      final widget = tester.widget<MakoloActionButton>(action);
      expect(widget.appearance, MakoloActionAppearance.primary);
      expect(widget.onPressed, isNotNull);
    },
  );

  testWidgets('Group 3 offer owner cursor keeps pagination callbacks', (
    tester,
  ) async {
    var nextOffset = -1;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: [
              SpaceWorkG3Depth(
                slug: 'boutique',
                ownerId: 'order-1',
                payload: const {
                  'kind': 'commerce_order',
                  'facts': {
                    'reference': 'CMD-42',
                    'currency': 'USD',
                    'total': '22.00',
                  },
                  'lines': {
                    'offset': 0,
                    'limit': 12,
                    'has_more': true,
                    'items': [],
                  },
                },
                onPageChange: (offset) => nextOffset = offset,
                onSecondaryPageChange: (_) {},
              ),
            ],
          ),
        ),
      ),
    );
    await tester.ensureVisible(find.text('Voir les suivants'));
    await tester.tap(find.text('Voir les suivants'));
    expect(nextOffset, 12);
    final button = find.widgetWithText(MakoloActionButton, 'Voir les suivants');
    expect(button, findsOneWidget);
  });

  testWidgets(
    'Group 3 G1 paginated realizations reuse owner-confirmed actions',
    (tester) async {
      var requestedOffset = -1;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpaceWorkG1Realizations(
              slug: 'community',
              payload: const {
                'items': [],
                'offset': 12,
                'limit': 12,
                'has_more': true,
              },
              onPageChange: (offset) => requestedOffset = offset,
            ),
          ),
        ),
      );
      final previous = find.widgetWithText(MakoloActionButton, 'Précédentes');
      final next = find.widgetWithText(
        MakoloActionButton,
        'Voir les suivantes',
      );
      expect(previous, findsOneWidget);
      expect(next, findsOneWidget);
      await tester.tap(previous);
      expect(requestedOffset, 0);
      await tester.tap(next);
      expect(requestedOffset, 24);
      expect(
        tester.widget<MakoloActionButton>(next).appearance,
        MakoloActionAppearance.secondary,
      );
    },
  );
}
