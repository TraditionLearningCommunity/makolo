import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/interaction_primitives.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  const open = MakoloInteractionAction(
    id: 'open',
    label: 'Ouvrir',
    intent: MakoloActionIntent.open,
  );
  const restricted = MakoloInteractionAction(
    id: 'restricted',
    label: 'Déplacer',
    intent: MakoloActionIntent.move,
    enabled: false,
  );

  test('every shared intent maps to a concrete icon', () {
    for (final intent in MakoloActionIntent.values) {
      expect(MakoloInteractionIcons.forIntent(intent), isA<IconData>());
    }
  });

  testWidgets(
    'menu shows only provided actions and does not dispatch disabled',
    (tester) async {
      final selected = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: Center(
              child: MakoloActionMenu(
                actions: const [open, restricted],
                onSelected: (action) => selected.add(action.id),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byTooltip('Actions'));
      await tester.pumpAndSettle();
      expect(find.text('Ouvrir'), findsOneWidget);
      expect(find.text('Déplacer'), findsOneWidget);

      final disabled = tester.widget<PopupMenuItem<String>>(
        find.widgetWithText(PopupMenuItem<String>, 'Déplacer'),
      );
      expect(disabled.enabled, isFalse);
      await tester.tap(find.text('Ouvrir'));
      await tester.pumpAndSettle();
      expect(selected, ['open']);
    },
  );

  testWidgets('menu without permitted actions renders no trigger', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MakoloActionMenu(actions: const [], onSelected: (_) {}),
        ),
      ),
    );
    expect(find.byType(PopupMenuButton<String>), findsNothing);
  });

  testWidgets('selection bar only appears with selection, can be exited', (
    tester,
  ) async {
    var cleared = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloSelectionBar(count: 2, onClear: () => cleared = true),
        ),
      ),
    );
    expect(find.text('2 sélectionnés'), findsOneWidget);
    await tester.tap(find.text('Terminer'));
    expect(cleared, isTrue);
    expect(find.byTooltip('Actions sur la sélection'), findsNothing);
  });

  testWidgets('zero selection renders no actions', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: MakoloSelectionBar(count: 0, onClear: () {})),
      ),
    );
    expect(find.text('Terminer'), findsNothing);
  });
}
