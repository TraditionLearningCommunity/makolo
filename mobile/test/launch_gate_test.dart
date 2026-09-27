import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_gate.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/splash/splash_screen.dart';

import 'fakes.dart';

class _MemoryLaunchPreferences implements LaunchPreferencesStore {
  _MemoryLaunchPreferences(this.snapshot, {this.readDelay = Duration.zero});

  LaunchPreferencesSnapshot snapshot;
  final Duration readDelay;

  @override
  Future<LaunchPreferencesSnapshot> read() async {
    if (readDelay > Duration.zero) {
      await Future<void>.delayed(readDelay);
    }
    return snapshot;
  }

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

Widget _app(
  AppRuntime runtime, {
  Duration minimumVisible = const Duration(milliseconds: 700),
}) {
  final router = createMakoloRouter(runtime, onAuthenticationChanged: () {});
  return MaterialApp.router(
    theme: buildMakoloTheme(),
    routerConfig: router,
    builder: (context, child) => LaunchGate(
      runtime: runtime,
      router: router,
      minimumVisible: minimumVisible,
      child: child ?? const SizedBox.shrink(),
    ),
  );
}

void main() {
  testWidgets('launch splash remains until the perceptible minimum', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      LaunchPreferencesSnapshot(
        hasCompletedOnboarding: true,
        lastBrandMomentAt: DateTime.now(),
      ),
    );
    final runtime = _runtime(preferences);

    await tester.pumpWidget(_app(runtime));
    expect(find.byType(SplashScreen), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 699));
    expect(find.byType(SplashScreen), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 2));
    await tester.pump();
    expect(find.byType(SplashScreen), findsNothing);
    expect(find.byKey(const Key('guest-public-landing')), findsOneWidget);
  });

  testWidgets('real initialization can keep splash longer than the minimum', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      LaunchPreferencesSnapshot(
        hasCompletedOnboarding: true,
        lastBrandMomentAt: DateTime.now(),
      ),
      readDelay: const Duration(milliseconds: 900),
    );
    final runtime = _runtime(preferences);

    await tester.pumpWidget(_app(runtime));
    await tester.pump(const Duration(milliseconds: 701));
    expect(find.byType(SplashScreen), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump();
    expect(find.byType(SplashScreen), findsNothing);
  });

  testWidgets(
    'new installation reaches concise onboarding then public landing',
    (tester) async {
      final preferences = _MemoryLaunchPreferences(
        LaunchPreferencesSnapshot(lastBrandMomentAt: DateTime.now()),
      );
      final runtime = _runtime(preferences);

      await tester.pumpWidget(_app(runtime));
      await tester.pumpAndSettle();

      expect(find.text('Découvrir.\nPréparer.\nAvancer.'), findsOneWidget);
      expect(find.text('Passer'), findsNothing);

      await tester.tap(find.text('Découvrir Makolo'));
      await tester.pumpAndSettle();

      expect(preferences.snapshot.hasCompletedOnboarding, isTrue);
      expect(find.byKey(const Key('guest-public-landing')), findsOneWidget);
    },
  );
}
