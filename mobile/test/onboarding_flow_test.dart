import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/onboarding/onboarding_flow.dart';

void main() {
  testWidgets('guest onboarding explains the progression before entry', (
    tester,
  ) async {
    OnboardingExit? exit;

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: OnboardingFlow(
          isAuthenticated: false,
          onComplete: (value) async => exit = value,
        ),
      ),
    );

    expect(find.text('Découvrez ce qui compte vraiment.'), findsOneWidget);
    expect(find.text('Continuer'), findsOneWidget);
    expect(find.text('1/3'), findsOneWidget);
    expect(find.text('Se connecter'), findsNothing);

    await tester.tap(find.text('Continuer'));
    await tester.pumpAndSettle();
    expect(find.text('Préparez ce qui peut l’être.'), findsOneWidget);
    expect(find.text('2/3'), findsOneWidget);

    await tester.tap(find.text('Continuer'));
    await tester.pumpAndSettle();
    expect(find.text('Avancez dans l’action réelle.'), findsOneWidget);
    expect(find.text('3/3'), findsOneWidget);
    expect(find.text('Découvrir Makolo'), findsOneWidget);
    expect(find.text('Se connecter'), findsOneWidget);
    expect(find.text('Créer un compte'), findsOneWidget);

    await tester.tap(find.text('Découvrir Makolo'));
    await tester.pump();

    expect(exit, OnboardingExit.continueGuest);
  });

  testWidgets('authenticated onboarding ends with contextual primary action', (
    tester,
  ) async {
    OnboardingExit? exit;

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: OnboardingFlow(
          isAuthenticated: true,
          onComplete: (value) async => exit = value,
        ),
      ),
    );

    await tester.tap(find.text('Continuer'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuer'));
    await tester.pumpAndSettle();

    expect(find.text('Ouvrir Makolo'), findsOneWidget);
    expect(find.text('Se connecter'), findsNothing);
    expect(find.text('Créer un compte'), findsNothing);

    await tester.tap(find.text('Ouvrir Makolo'));
    await tester.pump();

    expect(exit, OnboardingExit.continueAuthenticated);
  });

  testWidgets('onboarding survives large text scale and small viewport', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(2)),
          child: OnboardingFlow(
            isAuthenticated: false,
            onComplete: (_) async {},
          ),
        ),
      ),
    );

    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(find.text('Continuer'), findsOneWidget);
  });
}
