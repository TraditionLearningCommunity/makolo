import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/onboarding/onboarding_flow.dart';

void main() {
  testWidgets('guest onboarding is concise and has no meaningless Skip', (
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
    expect(find.text('Passer'), findsNothing);
    expect(find.text('Continuer'), findsNothing);
    expect(find.text('Services'), findsNothing);
    expect(find.text('Transports'), findsNothing);
    expect(find.text('Événements'), findsNothing);
    expect(find.text('Découvrir Makolo'), findsOneWidget);
    expect(find.text('Se connecter'), findsOneWidget);
    expect(find.text('Créer un compte'), findsOneWidget);

    await tester.tap(find.text('Découvrir Makolo'));
    await tester.pump();

    expect(exit, OnboardingExit.continueGuest);
  });

  testWidgets('authenticated onboarding has one contextual primary action', (
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

    expect(tester.takeException(), isNull);
    expect(find.text('Découvrir Makolo'), findsOneWidget);
  });
}
