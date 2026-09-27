import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/onboarding/onboarding_flow.dart';

void main() {
  testWidgets('first onboarding page stays concise and can be skipped', (
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

    expect(find.text('Découvrir.\nPréparer.\nAvancer.'), findsOneWidget);
    expect(find.text('Services'), findsOneWidget);
    expect(find.text('Transports'), findsOneWidget);
    expect(find.text('Événements'), findsOneWidget);

    await tester.tap(find.text('Passer'));
    await tester.pump();

    expect(exit, OnboardingExit.skip);
  });

  testWidgets('onboarding offers sign-in, account creation and guest mode', (
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

    await tester.tap(find.text('Continuer'));
    await tester.pump();

    expect(find.text('Se connecter'), findsOneWidget);
    expect(find.text('Créer un compte'), findsOneWidget);
    expect(find.text('Continuer sans compte'), findsOneWidget);

    await tester.tap(find.text('Continuer sans compte'));
    await tester.pump();

    expect(exit, OnboardingExit.continueGuest);
  });

  testWidgets('onboarding survives large text scale', (tester) async {
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

    expect(tester.takeException(), isNull);
    expect(find.text('Découvrir.\nPréparer.\nAvancer.'), findsOneWidget);
  });
}
