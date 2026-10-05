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
  Duration minimumVisible = Duration.zero,
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
  testWidgets('launch has no artificial splash delay', (tester) async {
    final preferences = _MemoryLaunchPreferences(
      LaunchPreferencesSnapshot(
        hasCompletedOnboarding: true,
        lastBrandMomentAt: DateTime.now(),
      ),
    );
    final runtime = _runtime(preferences);

    await tester.pumpWidget(_app(runtime));
    await tester.pump();

    expect(find.byType(SplashScreen), findsNothing);
    expect(find.byKey(const Key('guest-public-landing')), findsOneWidget);
  });

  testWidgets('real initialization keeps splash while preparation runs', (
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

  testWidgets('eligible launch plays Brand Moment before destination', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
    );
    final runtime = _runtime(preferences);

    await tester.pumpWidget(_app(runtime));
    await tester.pump();

    expect(find.byType(BrandMoment), findsOneWidget);
    expect(find.byKey(const Key('guest-public-landing')), findsNothing);

    await tester.pump(const Duration(seconds: 1));
    await tester.pump();

    expect(find.byType(BrandMoment), findsNothing);
    expect(find.byKey(const Key('guest-public-landing')), findsOneWidget);
    expect(preferences.snapshot.lastBrandMomentAt, isNotNull);
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
        find.text('Now n’est pas disponible pour le moment.'),
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
        find.text('Now n’est pas disponible pour le moment.'),
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
