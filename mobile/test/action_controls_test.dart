import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  testWidgets('Group 1 primary action uses shared theme and 48dp target', (
    tester,
  ) async {
    var invoked = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloActionButton(
            label: 'Continuer',
            onPressed: () => invoked++,
            appearance: MakoloActionAppearance.primary,
          ),
        ),
      ),
    );
    final button = find.byType(FilledButton);
    expect(button, findsOneWidget);
    expect(tester.getSize(button).height, greaterThanOrEqualTo(48));
    await tester.tap(find.text('Continuer'));
    expect(invoked, 1);
  });

  testWidgets('Group 1 quiet retry preserves action and accessible label', (
    tester,
  ) async {
    var retried = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloActionButton(
            label: 'Réessayer',
            onPressed: () => retried = true,
            appearance: MakoloActionAppearance.quiet,
            icon: Icons.refresh_rounded,
          ),
        ),
      ),
    );
    expect(find.byType(TextButton), findsOneWidget);
    await tester.tap(find.text('Réessayer'));
    expect(retried, isTrue);
  });

  testWidgets('Group 1 owner-disabled controls never invoke callbacks', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: MakoloActionButton(
            label: 'Indisponible',
            onPressed: null,
            appearance: MakoloActionAppearance.secondary,
          ),
        ),
      ),
    );
    final button = tester.widget<OutlinedButton>(find.byType(OutlinedButton));
    expect(button.onPressed, isNull);
    expect(find.text('Indisponible'), findsOneWidget);
  });

  testWidgets('Group 1 busy action cannot submit twice', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloActionButton(
            label: 'Envoi…',
            busy: true,
            onPressed: () => calls++,
            appearance: MakoloActionAppearance.primary,
          ),
        ),
      ),
    );
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
    expect(calls, 0);
  });

  testWidgets('Group 1 icon-only action announces its purpose', (tester) async {
    var called = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloIconActionButton(
            tooltip: 'Modifier mon profil',
            icon: Icons.edit_outlined,
            onPressed: () => called = true,
          ),
        ),
      ),
    );
    final action = find.byTooltip('Modifier mon profil');
    expect(action, findsOneWidget);
    expect(
      tester.getSize(find.byType(IconButton)).height,
      greaterThanOrEqualTo(48),
    );
    await tester.tap(action);
    expect(called, isTrue);
  });
}
