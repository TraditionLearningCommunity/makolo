import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/resumable_interaction_store.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
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
    interactions: ResumableInteractionStore.memory(),
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
  String? initialEmail,
  bool startWithAccounts = false,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
          child: LoginScreen(
            runtime: runtime,
            initialEmail: initialEmail,
            startWithAccounts: startWithAccounts,
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
}

http.Response _meResponse() {
  return http.Response(
    jsonEncode({
      'id': 'profile-a',
      'email': 'amina@example.com',
      'username': 'amina',
      'full_name': 'Amina K.',
    }),
    200,
  );
}

void main() {
  testWidgets('login stores the authenticated Profile and device account', (
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
        return _meResponse();
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
    await _tapVisible(tester, find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    final session = await tokens.readSession();
    expect(session?.profileId, 'profile-a');
    expect(session?.refreshToken, 'refresh-a');
    expect((await tokens.listAccounts()).single.email, 'amina@example.com');
  });

  testWidgets('quick access is opt-in and never requires a stored password', (
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
      if (request.url.path.endsWith('/auth/me/')) return _meResponse();
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
    await _tapVisible(tester, find.text('Se souvenir de moi').first);
    await _tapVisible(tester, find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    final account = (await tokens.listAccounts()).single;
    expect(account.hasQuickAccess, isTrue);
    expect(await tokens.readAccountSession('profile-a'), isNotNull);
  });

  testWidgets('invalid login keeps input and shows a human error', (
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
    await _tapVisible(tester, find.byKey(const Key('login-submit')));
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
      if (request.url.path.endsWith('/auth/me/')) return _meResponse();
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
    final submit = find.byKey(const Key('login-submit'));
    await tester.ensureVisible(submit);
    await tester.pumpAndSettle();
    await tester.tap(submit);
    await tester.tap(submit);
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
    EditableText password = tester.widget(
      find.descendant(
        of: find.byKey(const Key('login-password')),
        matching: find.byType(EditableText),
      ),
    );
    expect(password.obscureText, isTrue);

    await tester.tap(find.byKey(const Key('login-password-toggle')));
    await tester.pump();

    password = tester.widget(
      find.descendant(
        of: find.byKey(const Key('login-password')),
        matching: find.byType(EditableText),
      ),
    );
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
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
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
    await tester.tap(find.byKey(const Key('signup-submit')));
    await tester.pump();

    expect(
      find.text('Les deux mots de passe doivent être identiques.'),
      findsOneWidget,
    );
    expect(requestCount, 0);
  });

  testWidgets('signup creates the account and authenticates immediately', (
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
      if (request.url.path.endsWith('/auth/login/')) {
        return http.Response(
          jsonEncode({'access': 'access-a', 'refresh': 'refresh-a'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/me/')) return _meResponse();
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
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
    await tester.tap(find.byKey(const Key('signup-submit')));
    await tester.pumpAndSettle();

    expect((await tokens.readSession())?.profileId, 'profile-a');
    expect(
      find.text('Votre compte est prêt. Connectez-vous pour continuer.'),
      findsNothing,
    );
    expect(payload?['email'], 'amina@example.com');
    expect(payload?['username'], 'amina');
    expect(payload?['password_confirm'], 'password-one');
    expect(payload?.containsKey('birth_date'), isFalse);
    expect(payload?.containsKey('country'), isFalse);
  });

  testWidgets('forgot password uses a neutral modal confirmation', (
    tester,
  ) async {
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
    await _tapVisible(tester, find.byKey(const Key('forgot-password-link')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('forgot-email')),
      'unknown@example.com',
    );
    await _tapVisible(tester, find.byKey(const Key('forgot-submit')));
    await tester.pumpAndSettle();

    expect(forgotCalls, 1);
    expect(find.text('Consultez votre boîte de réception'), findsOneWidget);
    expect(find.textContaining('unknown@example.com'), findsOneWidget);
    expect(find.textContaining('n’existe pas'), findsNothing);
    expect(find.textContaining('existe bien'), findsNothing);
  });

  testWidgets('account switch opens the device account chooser', (
    tester,
  ) async {
    final recovery = SessionRecoveryController();
    final tokens = MemoryTokenStore();
    await tokens.saveAccount(
      DeviceAccount(
        profileId: 'profile-a',
        email: 'amina@example.com',
        displayName: 'Amina K.',
        hasQuickAccess: false,
        lastUsedAt: DateTime.utc(2026, 9, 27),
      ),
    );
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(
      tokens: tokens,
      client: client,
      recovery: recovery,
    );

    await _pumpLogin(tester, runtime, startWithAccounts: true);

    expect(find.text('Choisir un compte'), findsOneWidget);
    expect(find.text('Amina K.'), findsOneWidget);
    expect(find.text('Mot de passe requis'), findsOneWidget);
    expect(find.text('Ajouter un compte'), findsOneWidget);
  });

  testWidgets('login restores only the non-sensitive email draft', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);
    await runtime.interactions!.save('login', {
      'email': 'restore@example.com',
      'password': 'must-not-survive',
    });

    await _pumpLogin(tester, runtime);
    await tester.pump();

    expect(find.text('restore@example.com'), findsOneWidget);
    expect(
      (await runtime.interactions!.read('login')).containsKey('password'),
      isFalse,
    );
    final password = tester.widget<EditableText>(
      find.descendant(
        of: find.byKey(const Key('login-password')),
        matching: find.byType(EditableText),
      ),
    );
    expect(password.controller.text, isEmpty);
  });

  testWidgets('signup restores safe fields without persisting passwords', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('signup-email')),
      'draft@example.com',
    );
    await tester.enterText(find.byKey(const Key('signup-username')), 'draftuser');
    await tester.enterText(find.byKey(const Key('signup-first-name')), 'Amina');
    await tester.enterText(find.byKey(const Key('signup-password')), 'secret-pass');
    await tester.pump(const Duration(milliseconds: 300));

    final draft = await runtime.interactions!.read('signup');
    expect(draft['email'], 'draft@example.com');
    expect(draft['username'], 'draftuser');
    expect(draft['first_name'], 'Amina');
    expect(draft.containsKey('password'), isFalse);

    await tester.pumpWidget(const SizedBox.shrink());
    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    expect(find.text('draft@example.com'), findsOneWidget);
    expect(find.text('draftuser'), findsOneWidget);
    final password = tester.widget<EditableText>(
      find.descendant(
        of: find.byKey(const Key('signup-password')),
        matching: find.byType(EditableText),
      ),
    );
    expect(password.controller.text, isEmpty);
  });

  testWidgets('auth copy is concise and uses explicit secondary actions', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    expect(find.text('Se souvenir de moi'), findsOneWidget);
    expect(find.text('Accès rapide sur cet appareil'), findsNothing);
    expect(find.text('Mot de passe oublié ?'), findsOneWidget);
    expect(find.byType(OutlinedButton), findsOneWidget);

    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();
    expect(find.text('Quelques informations suffisent pour commencer avec Makolo.'), findsNothing);
    expect(find.text('Votre accès'), findsNothing);
    expect(find.text('Vous'), findsNothing);
    expect(find.text('Sécurité'), findsNothing);
    expect(find.text('J’ai déjà un compte'), findsOneWidget);
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
      if (request.url.path.endsWith('/auth/me/')) return _meResponse();
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
    await _tapVisible(tester, find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    expect(recovery.initialLocation(), '/journeys/123');
    expect(recovery.initialLocation(), '/now');
  });

  testWidgets('entry remains usable with large text', (tester) async {
    final tokens = MemoryTokenStore();
    final client = MockClient(
      (request) async => http.Response(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime, textScale: 2);
    expect(tester.takeException(), isNull);
    expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
    expect(find.byKey(const Key('login-submit')), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('login-password-toggle')));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Afficher le mot de passe'), findsOneWidget);
  });
}
