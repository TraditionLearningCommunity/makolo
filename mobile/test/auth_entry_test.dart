import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/auth/auth_error_messages.dart';
import 'package:makolo_mobile/features/auth/login_screen.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
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
      dio: client.dio,
      tokenStore: tokens,
    ),
  );
}

Future<void> _pumpLogin(
  WidgetTester tester,
  AppRuntime runtime, {
  double textScale = 1,
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

MockResponse _meResponse() {
  return MockResponse(
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
        return MockResponse(
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
    final account = (await tokens.listAccounts()).single;
    expect(account.username, 'amina');
    expect(account.email, 'amina@example.com');
  });

  testWidgets('login accepts the canonical Makolo identifier', (tester) async {
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/login/')) {
        expect(jsonDecode(request.body), {
          'username': '@amina',
          'password': 'secret-pass',
        });
        return MockResponse(
          jsonEncode({'access': 'access-a', 'refresh': 'refresh-a'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/me/')) return _meResponse();
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await tester.enterText(find.byKey(const Key('login-email')), '@amina');
    await tester.enterText(
      find.byKey(const Key('login-password')),
      'secret-pass',
    );
    await _tapVisible(tester, find.byKey(const Key('login-submit')));
    await tester.pumpAndSettle();

    expect((await tokens.readSession())?.profileId, 'profile-a');
    expect((await tokens.listAccounts()).single.publicIdentifier, '@amina');
  });

  testWidgets('quick access is opt-in and never requires a stored password', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/login/')) {
        return MockResponse(
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
          MockResponse(jsonEncode({'detail': 'No active account found'}), 401),
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
      find.text(
        'Identifiant Makolo, adresse e-mail ou mot de passe incorrect.',
      ),
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
        return MockResponse(
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
      (request) async => MockResponse(jsonEncode({}), 500),
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
    var registrationRequests = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/identifier/availability/')) {
        return MockResponse(jsonEncode({'available': true}), 200);
      }
      if (request.url.path.endsWith('/auth/register/')) {
        registrationRequests += 1;
      }
      return MockResponse(jsonEncode({}), 500);
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
    expect(registrationRequests, 0);
  });

  testWidgets('signup does not probe e-mail availability', (tester) async {
    var availabilityCalls = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/identifier/availability/')) {
        availabilityCalls += 1;
        return MockResponse(jsonEncode({'available': true}), 200);
      }
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
    await tester.pump(const Duration(milliseconds: 700));

    expect(availabilityCalls, 0);
  });

  testWidgets('locally invalid identifier never hits availability API', (
    tester,
  ) async {
    var availabilityCalls = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/identifier/availability/')) {
        availabilityCalls += 1;
      }
      return MockResponse(jsonEncode({}), 500);
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('signup-username')), 'a');
    await tester.pump(const Duration(milliseconds: 700));

    expect(availabilityCalls, 0);
  });

  testWidgets('signup checks Makolo identifier after debounce', (tester) async {
    var availabilityCalls = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/identifier/availability/')) {
        availabilityCalls += 1;
        expect(request.url.queryParameters['value'], 'amina');
        return MockResponse(
          jsonEncode({'available': true, 'username': 'amina'}),
          200,
        );
      }
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('signup-username')), 'amina');
    await tester.pump(const Duration(milliseconds: 399));
    expect(availabilityCalls, 0);
    expect(find.text('Vérification…'), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 2));
    await tester.pump();

    expect(availabilityCalls, 1);
    expect(find.text('Identifiant Makolo disponible.'), findsOneWidget);
  });

  testWidgets('stale identifier response never overwrites latest value', (
    tester,
  ) async {
    final firstResponse = Completer<MockResponse>();
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (!request.url.path.endsWith('/auth/identifier/availability/')) {
        throw StateError('unexpected request');
      }
      final value = request.url.queryParameters['value'];
      if (value == 'amina') return firstResponse.future;
      if (value == 'amina-new') {
        return MockResponse(
          jsonEncode({'available': true, 'username': 'amina-new'}),
          200,
        );
      }
      throw StateError('unexpected value $value');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('signup-username')), 'amina');
    await tester.pump(const Duration(milliseconds: 401));
    await tester.enterText(
      find.byKey(const Key('signup-username')),
      'amina-new',
    );
    await tester.pump(const Duration(milliseconds: 401));
    await tester.pump();

    expect(find.text('Identifiant Makolo disponible.'), findsOneWidget);

    firstResponse.complete(
      MockResponse(jsonEncode({'available': false, 'username': 'amina'}), 200),
    );
    // Let Dio finish its response-interceptor turn as well as the widget
    // future. A single pump can leave Dio's zero-duration completion timer
    // pending even though the stale-result assertion already holds.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));

    expect(find.text('Identifiant Makolo disponible.'), findsOneWidget);
    expect(
      find.text('Cet Identifiant Makolo n’est pas disponible.'),
      findsNothing,
    );
  });

  test(
    'transport failure defaults to Makolo unavailability without offline proof',
    () async {
      final message = await resolvedAuthErrorMessage(
        const MakoloTransportError('makolo_unreachable', 'unreachable'),
        fallback: 'fallback',
        offlineProbe: () async => false,
      );

      expect(message, makoloServerUnavailableMessage);
    },
  );

  test('established device offline state is allowed to name offline', () async {
    final message = await resolvedAuthErrorMessage(
      const MakoloTransportError('makolo_unreachable', 'unreachable'),
      fallback: 'fallback',
      offlineProbe: () async => true,
    );

    expect(message, deviceOfflineMessage);
  });

  testWidgets('signup creates the account and authenticates immediately', (
    tester,
  ) async {
    Map<String, dynamic>? payload;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/register/')) {
        payload = jsonDecode(request.body) as Map<String, dynamic>;
        return MockResponse(
          jsonEncode({'message': 'Compte créé.', 'user': {}}),
          201,
        );
      }
      if (request.url.path.endsWith('/auth/login/')) {
        return MockResponse(
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

  testWidgets('signup works without email and signs in with username', (
    tester,
  ) async {
    Map<String, dynamic>? registration;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/identifier/availability/')) {
        return MockResponse(
          jsonEncode({'available': true, 'username': 'sansmail'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/register/')) {
        registration = jsonDecode(request.body) as Map<String, dynamic>;
        return MockResponse(
          jsonEncode({'message': 'Compte créé.', 'user': {}}),
          201,
        );
      }
      if (request.url.path.endsWith('/auth/login/')) {
        expect(jsonDecode(request.body), {
          'username': 'sansmail',
          'password': 'password-one',
        });
        return MockResponse(
          jsonEncode({'access': 'access-a', 'refresh': 'refresh-a'}),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/me/')) {
        return MockResponse(
          jsonEncode({
            'id': 'profile-no-email',
            'email': null,
            'username': 'sansmail',
            'full_name': '',
          }),
          200,
        );
      }
      throw StateError('unexpected request');
    });
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime);
    await _tapVisible(tester, find.byKey(const Key('create-account-link')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('signup-username')),
      'sansmail',
    );
    await tester.pump(const Duration(milliseconds: 401));
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

    expect(registration?.containsKey('email'), isFalse);
    final account = (await tokens.listAccounts()).single;
    expect(account.username, 'sansmail');
    expect(account.email, isNull);
    expect(account.publicIdentifier, '@sansmail');
    expect((await tokens.readSession())?.profileId, 'profile-no-email');
  });

  testWidgets('forgot password uses a neutral modal confirmation', (
    tester,
  ) async {
    var forgotCalls = 0;
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/password/forgot/')) {
        forgotCalls += 1;
        return MockResponse(
          jsonEncode({
            'message': 'Demande de réinitialisation traitée.',
            'email_delivery': 'external',
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
    expect(find.textContaining('dossier spam'), findsOneWidget);
    expect(find.textContaining('n’existe pas'), findsNothing);
    expect(find.textContaining('existe bien'), findsNothing);
  });

  testWidgets(
    'password reset explains when this environment cannot deliver mail',
    (tester) async {
      final tokens = MemoryTokenStore();
      final client = MockClient((request) async {
        if (request.url.path.endsWith('/auth/password/forgot/')) {
          return MockResponse(
            jsonEncode({
              'message': 'Demande traitée.',
              'email_delivery': 'local_only',
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
        'amina@example.com',
      );
      await _tapVisible(tester, find.byKey(const Key('forgot-submit')));
      await tester.pumpAndSettle();

      expect(
        find.textContaining(
          'ne délivre pas encore les e-mails vers une boîte réelle',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('dossier spam'), findsNothing);
    },
  );

  testWidgets('signup explains an email already linked to an account', (
    tester,
  ) async {
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/register/')) {
        return MockResponse(
          jsonEncode({
            'email': ['User with this email already exists.'],
          }),
          400,
        );
      }
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
    await tester.enterText(find.byKey(const Key('signup-username')), 'amina-2');
    await tester.enterText(
      find.byKey(const Key('signup-password')),
      'Strong-registration-password-2026!',
    );
    await tester.enterText(
      find.byKey(const Key('signup-password-confirm')),
      'Strong-registration-password-2026!',
    );
    await tester.ensureVisible(find.byKey(const Key('signup-submit')));
    await tester.tap(find.byKey(const Key('signup-submit')));
    await tester.pumpAndSettle();

    expect(find.textContaining('déjà associée à un compte'), findsOneWidget);
    expect(find.textContaining('Mot de passe oublié'), findsWidgets);
  });

  testWidgets('account switch opens the device account chooser', (
    tester,
  ) async {
    final recovery = SessionRecoveryController()..markAccountSwitch();
    final tokens = MemoryTokenStore();
    await tokens.saveAccount(
      DeviceAccount(
        profileId: 'profile-a',
        username: 'amina',
        email: 'amina@example.com',
        displayName: 'Amina K.',
        hasQuickAccess: false,
        lastUsedAt: DateTime.utc(2026, 9, 27),
      ),
    );
    final client = MockClient(
      (request) async => MockResponse(jsonEncode({}), 500),
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

  testWidgets('expired session explains reconnect and preserves route once', (
    tester,
  ) async {
    final recovery = SessionRecoveryController()
      ..rememberLocation('/journeys/123')
      ..markSessionExpired();
    final tokens = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/login/')) {
        return MockResponse(
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
      (request) async => MockResponse(jsonEncode({}), 500),
    );
    final runtime = _runtime(tokens: tokens, client: client);

    await _pumpLogin(tester, runtime, textScale: 2);
    expect(tester.takeException(), isNull);
    expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
    expect(find.text('Makolo marche pour vous.'), findsOneWidget);
    expect(find.text('Makolo marche avec vous.'), findsNothing);
    expect(find.text('Identifiant Makolo ou adresse e-mail'), findsOneWidget);
    expect(find.text('Mot de passe'), findsOneWidget);
    expect(find.byKey(const Key('login-submit')), findsOneWidget);

    await tester.ensureVisible(find.byKey(const Key('login-password-toggle')));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Afficher le mot de passe'), findsOneWidget);
  });
}
