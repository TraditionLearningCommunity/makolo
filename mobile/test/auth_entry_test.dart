import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/auth/login_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

AppRuntime _runtime({
  required MemoryTokenStore tokens,
  required MockClient client,
  SessionRecoveryController? recovery,
}) {
  return AppRuntime(
    tokens: tokens,
    session: tokens.session,
    recovery: recovery ?? SessionRecoveryController(),
    api: MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      httpClient: client,
      tokenStore: tokens,
    ),
  );
}

Future<void> _pumpLogin(
  WidgetTester tester,
  AppRuntime runtime, {
  double textScale = 1,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
          child: LoginScreen(runtime: runtime),
        ),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets('login success stores the authenticated Profile identity', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/login/')) {
        return http.Response(
          jsonEncode({'access': 'access-a', 'refresh': 'refresh-a'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/me/')) {
        expect(request.headers['Authorization'], 'Bearer access-a');
        return http.Response(jsonEncode({'id': 'profile-a'}), 200);
      }
      throw StateError('unexpected request: ${request.url.path}');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.enterText(
      find.byKey(const Key('login-email')),
      'amina@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('login-password')),
      'secret-pass',
    );
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    final session = await tokens.readSession();
    expect(session?.profileId, 'profile-a');
    expect(session?.refreshToken, 'refresh-a');
  });

  testWidgets('invalid login keeps the user input and shows a human error', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async =>
          http.Response(jsonEncode({'detail': 'No active account found'}), 401),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.enterText(
      find.byKey(const Key('login-email')),
      'amina@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('login-password')),
      'wrong-pass',
    );
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    expect(
      find.text('Adresse e-mail ou mot de passe incorrect.'),
      findsOneWidget,
    );
    expect(find.text('amina@example.com'), findsOneWidget);
    expect(find.text('wrong-pass'), findsOneWidget);
    expect(find.textContaining('No active account'), findsNothing);
  });

  testWidgets('login cannot be submitted twice while busy', (tester) async {
    var loginCalls = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/login/')) {
        loginCalls += 1;
        await Future<void>.delayed(const Duration(milliseconds: 80));
        return http.Response(
          jsonEncode({'access': 'access-a', 'refresh': 'refresh-a'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/me/')) {
        return http.Response(jsonEncode({'id': 'profile-a'}), 200);
      }
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.enterText(
      find.byKey(const Key('login-email')),
      'amina@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('login-password')),
      'secret-pass',
    );
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pumpAndSettle();

    expect(loginCalls, 1);
  });

  testWidgets('password visibility can be toggled', (tester) async {
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    TextField password = tester.widget(find.byKey(const Key('login-password')));
    expect(password.obscureText, isTrue);

    await tester.tap(find.byKey(const Key('login-password-toggle')));
    await tester.pump();

    password = tester.widget(find.byKey(const Key('login-password')));
    expect(password.obscureText, isFalse);
  });

  testWidgets('signup validation prevents an invalid request', (tester) async {
    var requestCount = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      requestCount += 1;
      return http.Response(jsonEncode({}), 500);
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.tap(find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('signup-email')),
      'amina@example.com',
    );
    await tester.enterText(find.byKey(const Key('signup-username')), 'amina');
    await tester.enterText(
      find.byKey(const Key('signup-password')),
      'password-one',
    );
    await tester.enterText(
      find.byKey(const Key('signup-password-confirm')),
      'password-two',
    );
    await tester.ensureVisible(find.byKey(const Key('signup-submit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('signup-submit')));
    await tester.pump();

    expect(
      find.text('Les deux mots de passe doivent être identiques.'),
      findsOneWidget,
    );
    expect(requestCount, 0);
  });

  testWidgets('signup success returns to login with email and feedback', (
    tester,
  ) async {
    Map<String, dynamic>? payload;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/register/')) {
        payload = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({'message': 'Compte créé.', 'user': {}}),
          201,
        );
      }
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.tap(find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('signup-email')),
      'amina@example.com',
    );
    await tester.enterText(find.byKey(const Key('signup-username')), 'amina');
    await tester.enterText(
      find.byKey(const Key('signup-password')),
      'password-one',
    );
    await tester.enterText(
      find.byKey(const Key('signup-password-confirm')),
      'password-one',
    );
    await tester.ensureVisible(find.byKey(const Key('signup-submit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('signup-submit')));
    await tester.pumpAndSettle();

    expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
    expect(
      find.text('Votre compte est prêt. Connectez-vous pour continuer.'),
      findsOneWidget,
    );
    expect(find.text('amina@example.com'), findsOneWidget);
    expect(payload?['email'], 'amina@example.com');
    expect(payload?['username'], 'amina');
    expect(payload?['password_confirm'], 'password-one');
    expect(payload?.containsKey('birth_date'), isFalse);
    expect(payload?.containsKey('country'), isFalse);
  });

  testWidgets('forgot password keeps the response neutral', (tester) async {
    var forgotCalls = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/password/forgot/')) {
        forgotCalls += 1;
        return http.Response(
          jsonEncode({
            'message': 'Si un compte actif correspond à cette adresse, un e-mail de réinitialisation a été envoyé.',
          }),
          200,
        );
      }
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.tap(find.byKey(const Key('forgot-password-link')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('forgot-email')),
      'unknown@example.com',
    );
    await tester.tap(find.byKey(const Key('forgot-submit')));
    await tester.pumpAndSettle();

    expect(forgotCalls, 1);
    expect(
      find.textContaining('Si un compte correspond à cette adresse'),
      findsWidgets,
    );
    expect(find.textContaining('n’existe pas'), findsNothing);
    expect(find.textContaining('existe bien'), findsNothing);
  });

  testWidgets('expired session explains reconnect and preserves route once', (
    tester,
  ) async {
    final recovery = SessionRecoveryController()
      ..rememberLocation('/journeys/123')
      ..markSessionExpired();
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/login/')) {
        return http.Response(
          jsonEncode({'access': 'new-access', 'refresh': 'new-refresh'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/me/')) {
        return http.Response(jsonEncode({'id': 'profile-a'}), 200);
      }
      throw StateError('unexpected request');
    });
    final runtime = _runtime(
      tokens: tokens,
      client: client,
      recovery: recovery,
    );

    await _pumpLogin(tester, runtime);
    expect(find.text('Reconnectez-vous pour continuer.'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('login-email')),
      'amina@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('login-password')),
      'secret-pass',
    );
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    expect(recovery.initialLocation(), '/journeys/123');
    expect(recovery.initialLocation(), '/now');
  });

  testWidgets('entry remains usable with large text', (tester) async {
    final semantics = tester.ensureSemantics();
    addTearDown(semantics.dispose);
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime, textScale: 2);
    expect(tester.takeException(), isNull);
    expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
    expect(find.byKey(const Key('login-submit')), findsOneWidget);
    expect(
      find.bySemanticsLabel(RegExp('Afficher le mot de passe')),
      findsOneWidget,
    );
  });
}
