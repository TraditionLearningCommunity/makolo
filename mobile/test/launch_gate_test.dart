import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_gate.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/splash/brand_moment.dart';
import 'package:makolo_mobile/features/splash/splash_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
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
  DateTime? launchStartedAt,
  Duration minimumVisible = const Duration(seconds: 1),
}) {
  final router = createMakoloRouter(runtime, onAuthenticationChanged: () {});
  return MaterialApp.router(
    theme: buildMakoloTheme(),
    routerConfig: router,
    builder: (context, child) => LaunchGate(
      runtime: runtime,
      router: router,
      launchStartedAt: launchStartedAt,
      minimumVisible: minimumVisible,
      child: child ?? const SizedBox.shrink(),
    ),
  );
}

void main() {
  testWidgets('launch splash remains visible for at least one second', (
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
    expect(find.byKey(const Key('animated-splash-mark')), findsOneWidget);
    expect(find.byType(BrandMoment), findsNothing);

    await tester.pump(const Duration(milliseconds: 999));
    expect(find.byType(SplashScreen), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 2));
    await tester.pump();
    expect(find.byType(SplashScreen), findsNothing);
    expect(find.byType(BrandMoment), findsNothing);
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
      readDelay: const Duration(milliseconds: 1200),
    );
    final runtime = _runtime(preferences);

    await tester.pumpWidget(_app(runtime));
    await tester.pump(const Duration(milliseconds: 1001));
    expect(find.byType(SplashScreen), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump();
    expect(find.byType(SplashScreen), findsNothing);
  });

  testWidgets(
    'new installation completes onboarding then reaches public landing',
    (tester) async {
      final preferences = _MemoryLaunchPreferences(
        LaunchPreferencesSnapshot(lastBrandMomentAt: DateTime.now()),
      );
      final runtime = _runtime(preferences);

      await tester.pumpWidget(
        _app(
          runtime,
          launchStartedAt: DateTime.now().subtract(const Duration(seconds: 1)),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Découvrez ce qui compte vraiment.'), findsOneWidget);

      await tester.tap(find.text('Continuer'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continuer'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Découvrir Makolo'));
      await tester.pumpAndSettle();

      expect(preferences.snapshot.hasCompletedOnboarding, isTrue);
      expect(find.byKey(const Key('guest-public-landing')), findsOneWidget);
    },
  );

  testWidgets(
    'authenticated launch stays local-first while acquisition fails',
    (tester) async {
      final preferences = _MemoryLaunchPreferences(
        LaunchPreferencesSnapshot(
          hasCompletedOnboarding: true,
          lastBrandMomentAt: DateTime.now(),
        ),
      );
      final database = MakoloDatabase.memory();
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final store = ProfileStore(database, 'profile-a');
      final remoteResponse = Completer<MockResponse>();
      var requests = 0;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((_) {
          requests += 1;
          return remoteResponse.future;
        }).dio,
      );
      final sync = SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: tokens.session,
        recovery: SessionRecoveryController(),
        launchPreferences: preferences,
        api: api,
        database: database,
        store: store,
        personal: PersonalRepository(store),
        sync: sync,
      );
      await tester.pumpWidget(
        _app(
          runtime,
          launchStartedAt: DateTime.now().subtract(const Duration(seconds: 1)),
          minimumVisible: Duration.zero,
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 1));
      await tester.pump();

      expect(find.byType(SplashScreen), findsNothing);
      expect(
        find.text('Pas encore disponible sur cet appareil'),
        findsOneWidget,
      );
      expect(requests, 1);

      remoteResponse.complete(
        const MockResponse(
          '{"error":{"code":"unavailable","message":"down"}}',
          503,
        ),
      );
      await tester.pumpAndSettle();

      expect(requests, greaterThanOrEqualTo(1));
      expect(
        find.text('Pas encore disponible sur cet appareil'),
        findsOneWidget,
      );

      // Unmount SyncLifecycle before the widget test fake clock stops. Its
      // Drift-backed subscriptions are live by design; closing the database
      // from addTearDown can deadlock after the clock is no longer advancing.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(seconds: 1));
      api.close();
    },
  );
}
