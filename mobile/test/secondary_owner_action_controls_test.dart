import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/design/interaction_primitives.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  testWidgets(
    'Group 2: secondary and primary actions invoke only supplied owners',
    (tester) async {
      final calls = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: Wrap(
              children: [
                MakoloActionButton(
                  label: 'Créer un dossier',
                  onPressed: () => calls.add('create'),
                  appearance: MakoloActionAppearance.primary,
                ),
                MakoloActionButton(
                  label: 'Rattacher un dossier',
                  onPressed: () => calls.add('link'),
                  appearance: MakoloActionAppearance.secondary,
                ),
                const MakoloActionButton(
                  label: 'Changer l’état',
                  onPressed: null,
                  appearance: MakoloActionAppearance.secondary,
                ),
              ],
            ),
          ),
        ),
      );
      await tester.tap(find.text('Créer un dossier'));
      await tester.tap(find.text('Rattacher un dossier'));
      final disabled = tester.widget<OutlinedButton>(
        find.widgetWithText(OutlinedButton, 'Changer l’état'),
      );
      expect(disabled.onPressed, isNull);
      expect(calls, ['create', 'link']);
    },
  );

  testWidgets(
    'Group 2: destructive action has error treatment, without implied success',
    (tester) async {
      var requested = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: MakoloActionButton(
              label: 'Révoquer le lien',
              appearance: MakoloActionAppearance.danger,
              onPressed: () => requested += 1,
            ),
          ),
        ),
      );
      final destructive = tester.widget<OutlinedButton>(
        find.widgetWithText(OutlinedButton, 'Révoquer le lien'),
      );
      expect(destructive.style, isNotNull);
      await tester.tap(find.text('Révoquer le lien'));
      expect(requested, 1);
    },
  );

  testWidgets('Group 2: owner-filtered menu cannot dispatch disabled actions', (
    tester,
  ) async {
    final selected = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloActionMenu(
            actions: const [
              MakoloInteractionAction(
                id: 'inspect',
                label: 'Voir le projet',
                intent: MakoloActionIntent.inspect,
              ),
              MakoloInteractionAction(
                id: 'revoke',
                label: 'Révoquer le mandat',
                intent: MakoloActionIntent.unlink,
                enabled: false,
                destructive: true,
              ),
            ],
            onSelected: (action) => selected.add(action.id),
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Actions'));
    await tester.pumpAndSettle();
    final blocked = tester.widget<PopupMenuItem<String>>(
      find.widgetWithText(PopupMenuItem<String>, 'Révoquer le mandat'),
    );
    expect(blocked.enabled, isFalse);
    await tester.tap(find.text('Voir le projet'));
    await tester.pumpAndSettle();
    expect(selected, ['inspect']);
  });

  testWidgets('Group 2: busy secondary form cannot double-submit', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MakoloActionButton(
            label: 'Enregistrement…',
            onPressed: () => calls += 1,
            busy: true,
            appearance: MakoloActionAppearance.primary,
          ),
        ),
      ),
    );
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
    expect(calls, 0);
  });
}
