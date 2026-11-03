import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/makolo_app.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/splash/splash_screen.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'fakes.dart';

class _Preferences implements LaunchPreferencesStore {
  @override
  Future<LaunchPreferencesSnapshot> read() async => LaunchPreferencesSnapshot(
    hasCompletedOnboarding: true,
    lastBrandMomentAt: DateTime.now(),
  );

  @override
  Future<void> setLastBrandMomentAt(DateTime value) async {}

  @override
  Future<void> setOnboardingCompleted() async {}
}

void main() {
  testWidgets(
    'runtime failure releases native splash to the recoverable error',
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
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appRuntimeProvider.overrideWith(
              (ref) async => throw StateError('local initialization failed'),
            ),
          ],
          child: const MakoloApp(),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Makolo n’a pas pu ouvrir'), findsOneWidget);
      expect(find.text('Réessayer'), findsOneWidget);
      expect(calls.map((call) => call.method), contains('ready'));
      expect(find.byType(SplashScreen), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'runtime replacement unmounts readers before using the new store',
    (tester) async {
      final replacement = Completer<AppRuntime>();
      final database = MakoloDatabase.memory();
      final store = ProfileStore(database, 'profile-a');
      await tester.runAsync(
        () => store.putProjection(
          kind: 'personal.now',
          schemaVersion: 1,
          payload: {'items': <Object>[]},
        ),
      );
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: const AuthSession(
          accessToken: 'test',
          refreshToken: 'test',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        launchPreferences: _Preferences(),
        database: database,
        personal: PersonalRepository(store),
      );
      var builds = 0;
      final container = ProviderContainer(
        overrides: [
          appRuntimeProvider.overrideWith((ref) async {
            if (builds++ == 0) {
              ref.onDispose(() => unawaited(runtime.close()));
              return runtime;
            }
            return replacement.future;
          }),
        ],
      );
      addTearDown(container.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MakoloApp(),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(NowScreen), findsOneWidget);

      container.invalidate(appRuntimeProvider);
      await tester.pump();
      expect(find.byType(NowScreen), findsNothing);
      expect(find.byType(SplashScreen), findsOneWidget);
      expect(tester.takeException(), isNull);

      replacement.complete(
        AppRuntime(
          tokens: MemoryTokenStore(),
          session: null,
          recovery: SessionRecoveryController(),
          launchPreferences: _Preferences(),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(NowScreen), findsNothing);
      expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
      expect(find.byKey(const Key('guest-login-action')), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );
}
