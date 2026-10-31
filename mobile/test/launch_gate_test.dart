import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_gate.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_mark.dart';
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

Widget _app(AppRuntime runtime) {
  final router = createMakoloRouter(runtime, onAuthenticationChanged: () {});

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
    'native splash releases after local preparation and a drawn destination',
    (tester) async {
      final calls = <MethodCall>[];
      const channel = MethodChannel('makolo/launch');
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (
        call,
      ) async {
        calls.add(call);
        return null;
      });
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          channel,
          null,
        ),
      );
      final preferences = _MemoryLaunchPreferences(
        const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
        readDelay: const Duration(milliseconds: 200),
      );
      await tester.pumpWidget(_app(_runtime(preferences)));
      expect(calls, isEmpty);
      await tester.pump(const Duration(milliseconds: 199));
      expect(calls, isEmpty);
      await tester.pump(const Duration(milliseconds: 2));
      await tester.pump();
      expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
      expect(calls.map((call) => call.method), ['ready']);
      await tester.pump();
      expect(calls.length, 1);
    },
  );
  testWidgets(
    'native branded launch does not replay a Flutter animation or add delay',
    (tester) async {
      final preferences = _MemoryLaunchPreferences(
        const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
      );
      await tester.pumpWidget(_app(_runtime(preferences)));
      await tester.pump();
      expect(find.byType(BrandMoment), findsNothing);
      expect(find.byKey(const Key('brand-footsteps')), findsNothing);
      expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
      expect(find.byType(SplashScreen), findsNothing);
    },
  );

  testWidgets(
    'preparation retains the static final mark without restarting launch',
    (tester) async {
      final preferences = _MemoryLaunchPreferences(
        const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
        readDelay: const Duration(milliseconds: 1800),
      );
      await tester.pumpWidget(_app(_runtime(preferences)));
      expect(find.byType(SplashScreen), findsOneWidget);
      expect(find.byType(MakoloMark), findsOneWidget);
      expect(find.byType(BrandMoment), findsNothing);
      await tester.pump(const Duration(milliseconds: 1250));
      expect(find.byType(SplashScreen), findsOneWidget);
      expect(find.byKey(const Key('brand-footsteps')), findsNothing);
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pump();
      expect(find.byType(SplashScreen), findsNothing);
      expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
    },
  );

  testWidgets('returning from background does not replay branding', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
    );
    final app = _app(_runtime(preferences));
    await tester.pumpWidget(app);
    await tester.pumpAndSettle();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(find.byType(BrandMoment), findsNothing);
    expect(find.byType(SplashScreen), findsNothing);
    expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
  });

  testWidgets('priority login route survives native branded launch', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
    );
    final runtime = _runtime(preferences);
    final router = createMakoloRouter(runtime, onAuthenticationChanged: () {});
    router.go('/login');
    await tester.pumpWidget(
      MaterialApp.router(
        routerConfig: router,
        builder: (context, child) =>
            LaunchGate(runtime: runtime, router: router, child: child!),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
    expect(find.byType(BrandMoment), findsNothing);
    expect(find.byKey(const Key('guest-public-home')), findsNothing);
  });

  testWidgets('new installation completes onboarding then reaches guest', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      const LaunchPreferencesSnapshot(),
    );

    await tester.pumpWidget(_app(_runtime(preferences)));

    await tester.pump();

    await tester.pump(const Duration(milliseconds: 1250));
    await tester.pumpAndSettle();

    expect(find.text('Makolo marche pour vous.'), findsOneWidget);

    await tester.tap(find.text('Continuer'));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('onboarding-location-skip')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('onboarding-primary')));
    await tester.pumpAndSettle();

    expect(preferences.snapshot.hasCompletedOnboarding, isTrue);

    expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
  });

  testWidgets('authenticated launch remains local-first on network failure', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
    );

    final database = MakoloDatabase.memory();
    addTearDown(database.close);

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

    await tester.pumpWidget(_app(runtime));

    await tester.pump();

    // Le lancement n'attend pas la fin d'une requête réseau.
    await tester.pump(const Duration(milliseconds: 1250));
    await tester.pump();

    expect(find.byType(BrandMoment), findsNothing);

    expect(find.text('Now indisponible.'), findsOneWidget);

    expect(requests, 1);

    remoteResponse.complete(
      const MockResponse(
        '{"error":{"code":"unavailable","message":"down"}}',
        503,
      ),
    );

    await tester.pumpAndSettle();

    expect(requests, greaterThanOrEqualTo(1));

    expect(find.text('Now indisponible.'), findsOneWidget);

    // Unmount live Drift subscriptions before disposal.
    await tester.pumpWidget(const SizedBox.shrink());

    await tester.pump(const Duration(seconds: 1));

    api.close();
  });

  testWidgets('reduce motion shows a static mark and completes launch', (
    tester,
  ) async {
    final preferences = _MemoryLaunchPreferences(
      const LaunchPreferencesSnapshot(hasCompletedOnboarding: true),
      readDelay: const Duration(milliseconds: 200),
    );

    final runtime = _runtime(preferences);

    final router = createMakoloRouter(runtime, onAuthenticationChanged: () {});

    await tester.pumpWidget(
      MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: LaunchGate(
            runtime: runtime,
            router: router,
            child: child ?? const SizedBox.shrink(),
          ),
        ),
      ),
    );

    await tester.pump();

    expect(find.byType(SplashScreen), findsOneWidget);
    expect(find.byType(MakoloMark), findsOneWidget);

    // Aucun pas animé lorsque Reduce Motion est actif.
    expect(find.byKey(const Key('brand-footsteps')), findsNothing);

    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump();

    expect(find.byType(BrandMoment), findsNothing);
    expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
  });
}
