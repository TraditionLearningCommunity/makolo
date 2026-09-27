import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/resumable_interaction_store.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/auth/login_screen.dart';
import 'package:makolo_mobile/features/auth/signup_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

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

AppRuntime _guestRuntime(
  SessionRecoveryController recovery, {
  MockClient? client,
}) {
  final tokens = MemoryTokenStore();
  return AppRuntime(
    tokens: tokens,
    session: null,
    recovery: recovery,
    launchPreferences: _MemoryLaunchPreferences(),
    interactions: ResumableInteractionStore.memory(),
    api: client == null
        ? null
        : MakoloApiClient(
            baseUri: Uri.parse('https://makolo.invalid/'),
            httpClient: client,
            tokenStore: tokens,
          ),
  );
}

GoRouter _router(AppRuntime runtime) {
  return createMakoloRouter(runtime, onAuthenticationChanged: () {});
}

Future<void> _pump(WidgetTester tester, GoRouter router) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('guest sees a standalone public landing without personal shell', (
    tester,
  ) async {
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/discovery/items/');
      return http.Response(
        jsonEncode({
          'data': {
            'results': [
              {
                'representation': {
                  'title': 'Possibilité réelle',
                  'summary': 'Résumé public.',
                  'eyebrow': 'Public',
                },
              },
            ],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );

    await _pump(tester, router);

    expect(find.byKey(const Key('guest-public-landing')), findsOneWidget);
    expect(find.text('Possibilité réelle'), findsOneWidget);
    expect(find.text('Now'), findsNothing);
    expect(find.text('En cours'), findsNothing);
    expect(find.text('Moi'), findsNothing);
    expect(find.byTooltip('Avatar'), findsNothing);
    expect(find.byTooltip('Makolo Mark'), findsNothing);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('empty public contract stays calm without invented cards', (
    tester,
  ) async {
    final client = MockClient(
      (request) async => http.Response(
        jsonEncode({
          'data': {'results': <Object>[]},
        }),
        200,
      ),
    );
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );

    await _pump(tester, router);

    expect(
      find.text('Aucune possibilité publique à afficher pour le moment.'),
      findsOneWidget,
    );
    expect(find.byType(Card), findsNothing);
  });

  testWidgets(
    'personal guest destination asks for auth without personal shell',
    (tester) async {
      final recovery = SessionRecoveryController();
      final router = _router(_guestRuntime(recovery));

      await _pump(tester, router);
      router.go('/ongoing');
      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.text('Connectez-vous pour continuer.'), findsOneWidget);
      expect(find.text('Now'), findsNothing);
      expect(find.text('En cours'), findsNothing);
      expect(find.byTooltip('Avatar'), findsNothing);
      expect(recovery.lastUsefulLocation, '/ongoing');
    },
  );

  testWidgets('login and create-account remain explicit public destinations', (
    tester,
  ) async {
    final router = _router(_guestRuntime(SessionRecoveryController()));

    await _pump(tester, router);

    router.go('/login');
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);

    router.go('/create-account');
    await tester.pumpAndSettle();
    expect(find.byType(SignupScreen), findsOneWidget);
  });

  testWidgets('protected deep destination is preserved for post-auth resume', (
    tester,
  ) async {
    final recovery = SessionRecoveryController();
    final router = _router(_guestRuntime(recovery));

    await _pump(tester, router);

    router.go('/journeys/journey-1');
    await tester.pumpAndSettle();

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.text('Connectez-vous pour continuer.'), findsOneWidget);
    expect(recovery.lastUsefulLocation, '/journeys/journey-1');
    expect(recovery.awaitingAuthentication, isTrue);
  });
}
