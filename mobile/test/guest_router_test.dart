import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/auth/login_screen.dart';
import 'package:makolo_mobile/features/auth/register_screen.dart';

import 'fakes.dart';

class _MemoryLaunchPreferences implements LaunchPreferencesStore {
  LaunchPreferencesSnapshot snapshot = const LaunchPreferencesSnapshot();

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

AppRuntime _guestRuntime(SessionRecoveryController recovery) {
  return AppRuntime(
    tokens: MemoryTokenStore(),
    session: null,
    recovery: recovery,
    launchPreferences: _MemoryLaunchPreferences(),
  );
}

void main() {
  testWidgets('guest starts on a useful Discover surface without forced login', (
    tester,
  ) async {
    final router = createMakoloRouter(
      _guestRuntime(SessionRecoveryController()),
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(
          theme: buildMakoloTheme(),
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?',
      ),
      findsOneWidget,
    );
    expect(find.byType(LoginScreen), findsNothing);

    router.go('/ongoing');
    await tester.pumpAndSettle();

    expect(find.text('En cours'), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('login and create-account routes are real destinations', (
    tester,
  ) async {
    final router = createMakoloRouter(
      _guestRuntime(SessionRecoveryController()),
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(
          theme: buildMakoloTheme(),
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    router.go('/login');
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);

    router.go('/create-account');
    await tester.pumpAndSettle();
    expect(find.byType(RegisterScreen), findsOneWidget);
  });

  testWidgets('protected deep destination is preserved instead of redirecting', (
    tester,
  ) async {
    final recovery = SessionRecoveryController();
    final router = createMakoloRouter(_guestRuntime(recovery));

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(
          theme: buildMakoloTheme(),
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    router.go('/journeys/journey-1');
    await tester.pumpAndSettle();

    expect(find.text('Connectez-vous pour continuer'), findsOneWidget);
    expect(recovery.lastUsefulLocation, '/journeys/journey-1');
  });
}
