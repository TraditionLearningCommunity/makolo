import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/auth_repository.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/auth/account_actions.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  test(
    'logout removes credentials even when the server is unavailable',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access-a',
          refreshToken: 'refresh-a',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: MockClient((request) async {
          throw Exception('offline');
        }).dio,
        tokenStore: tokens,
      );

      await AuthRepository(api, tokens).logout();

      expect(await tokens.readSession(), isNull);
    },
  );

  test(
    'account switch preserves Profile data and keeps Profiles isolated',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final profileA = ProfileStore(database, 'profile-a');
      final profileB = ProfileStore(database, 'profile-b');
      await profileA.putProjection(
        kind: 'personal.me',
        schemaVersion: 1,
        payload: {
          'items': ['kept'],
        },
      );

      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access-a',
          refreshToken: 'refresh-a',
          profileId: 'profile-a',
        ),
      );
      final recovery = SessionRecoveryController()
        ..rememberLocation('/ongoing')
        ..markAccountSwitch();
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: MockClient((request) async {
          throw Exception('offline');
        }).dio,
        tokenStore: tokens,
      );

      await AuthRepository(api, tokens).logout();

      expect(await tokens.readSession(), isNull);
      expect((await profileA.readProjection('personal.me'))?.payload['items'], [
        'kept',
      ]);
      expect(await profileB.readProjection('personal.me'), isNull);
      expect(recovery.entryReason, EntryReason.accountSwitch);
      expect(recovery.lastUsefulLocation, isNull);
    },
  );

  testWidgets(
    'account action opens chooser without destroying current session',
    (tester) async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access-a',
        refreshToken: 'refresh-a',
        profileId: 'profile-a',
      ),
    );
    final recovery = SessionRecoveryController();
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/logout/')) {
        return MockResponse(jsonEncode({'message': 'ok'}), 200);
      }
      throw StateError('unexpected request');
    });
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      dio: client.dio,
      tokenStore: tokens,
    );
    var authenticationChanges = 0;
    final runtime = AppRuntime(
      tokens: tokens,
      session: tokens.session,
      recovery: recovery,
      api: api,
    );

    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => Scaffold(
            body: AccountActionsButton(
              runtime: runtime,
              onAuthenticationChanged: () => authenticationChanges += 1,
            ),
          ),
        ),
        GoRoute(
          path: '/accounts',
          builder: (context, state) =>
              const Scaffold(body: Text('Choisir un compte')),
        ),
      ],
    );

    await tester.pumpWidget(MaterialApp.router(routerConfig: router));

    await tester.tap(find.byKey(const Key('account-actions')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Changer de compte'));
    await tester.pumpAndSettle();

    expect(find.text('Choisir un compte'), findsOneWidget);
    expect((await tokens.readSession())?.profileId, 'profile-a');
    expect(authenticationChanges, 0);
      expect(recovery.entryReason, EntryReason.accountSwitch);
    },
  );
}
