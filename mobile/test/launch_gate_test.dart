import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_gate.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

import 'fakes.dart';

class _MemoryLaunchPreferences implements LaunchPreferencesStore {
  _MemoryLaunchPreferences(this.snapshot);

  LaunchPreferencesSnapshot snapshot;

  @override
  Future<LaunchPreferencesSnapshot> read() async => snapshot;

  @override
  Future<void> setLastBrandMomentAt(DateTime value) async {
    snapshot = snapshot.copyWith(lastBrandMomentAt: value);
  }

  @override
  Future<void> setOnboardingCompleted() async {
    snapshot = snapshot.copyWith(hasCompletedOnboarding: true);
  }
}

AppRuntime _runtime(_MemoryLaunchPreferences preferences) {
  return AppRuntime(
    tokens: MemoryTokenStore(),
    session: null,
    recovery: SessionRecoveryController(),
    launchPreferences: preferences,
  );
}

Widget _app(AppRuntime runtime) {
  final router = createMakoloRouter(
    runtime,
    onAuthenticationChanged: () {},
  );
  return MaterialApp.router(
    theme: buildMakoloTheme(),
    routerConfig: router,
    builder: (context, child) => LaunchGate(
      runtime: runtime,
      router: router,
      child: child ?? const SizedBox.shrink(),
    ),
  );
}

void main() {
  testWidgets(
    'new installation shows onboarding and Skip exits to guest mode',
    (tester) async {
      final preferences = _MemoryLaunchPreferences(
        LaunchPreferencesSnapshot(lastBrandMomentAt: DateTime.now()),
      );
      final runtime = _runtime(preferences);

      await tester.pumpWidget(_app(runtime));
      await tester.pumpAndSettle();

      expect(find.text('Découvrir.\nPréparer.\nAvancer.'), findsOneWidget);

      await tester.tap(find.text('Passer'));
      await tester.pumpAndSettle();

      expect(preferences.snapshot.hasCompletedOnboarding, isTrue);
      expect(
        find.text(
          'Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets('completed onboarding does not return on normal launch', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      LaunchPreferencesSnapshot(
        hasCompletedOnboarding: true,
        lastBrandMomentAt: DateTime.now(),
      ),
    );

    await tester.pumpWidget(_app(_runtime(preferences)));
    await tester.pumpAndSettle();

    expect(find.text('Découvrir.\nPréparer.\nAvancer.'), findsNothing);
    expect(
      find.text(
        'Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?',
      ),
      findsOneWidget,
    );
  });
}
