import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/makolo_app.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Future<void> _pumpUntil(
  WidgetTester tester,
  Finder finder, {
  Duration timeout = const Duration(seconds: 5),
}) async {
  final deadline = DateTime.now().add(timeout);
  while (finder.evaluate().isEmpty && DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 50));
    final exception = tester.takeException();
    if (exception != null) throw exception;
  }
  expect(finder, findsOneWidget);
}

void main() {
  testWidgets(
    'successful login rebuilds the authenticated runtime and opens Now',
    (tester) async {
      final directory = await Directory.systemTemp.createTemp(
        'makolo-post-login-',
      );
      addTearDown(() => directory.delete(recursive: true));
      final launchPreferences = FileLaunchPreferencesStore.forFile(
        File('${directory.path}/launch.json'),
      );
      await launchPreferences.setOnboardingCompleted();

      final tokens = MemoryTokenStore();
      final recovery = SessionRecoveryController()
        ..requireAuthentication('/now');
      final handler = MockClient((request) async {
        if (request.url.path.endsWith('/auth/login/')) {
          return MockResponse(
            jsonEncode({'access': 'access-a', 'refresh': 'refresh-a'}),
            200,
          );
        }
        if (request.url.path.endsWith('/auth/me/')) {
          return MockResponse(
            jsonEncode({
              'id': 'profile-a',
              'email': null,
              'username': 'amina',
              'full_name': '',
            }),
            200,
          );
        }
        throw StateError('unexpected request ${request.url.path}');
      });

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appRuntimeProvider.overrideWith((ref) async {
              final session = await tokens.readSession();
              final api = MakoloApiClient(
                baseUri: Uri.parse('https://makolo.invalid/'),
                dio: handler.dio,
                tokenStore: tokens,
              );
              if (session?.profileId == null) {
                return AppRuntime(
                  tokens: tokens,
                  session: session,
                  recovery: recovery,
                  launchPreferences: launchPreferences,
                  api: api,
                );
              }
              return AppRuntime(
                tokens: tokens,
                session: session,
                recovery: recovery,
                launchPreferences: launchPreferences,
                api: api,
                personal: _HandoffPersonalRepository(),
              );
            }),
          ],
          child: const MakoloApp(),
        ),
      );
      await _pumpUntil(tester, find.text('Connectez-vous à Makolo'));

      expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
      await tester.enterText(find.byKey(const Key('login-email')), '@amina');
      await tester.enterText(
        find.byKey(const Key('login-password')),
        'secret-pass',
      );
      await tester.tap(find.byKey(const Key('login-submit')));
      await _pumpUntil(tester, find.text('Tout est en ordre. ✓'));

      expect(find.text('Tout est en ordre. ✓'), findsOneWidget);
      expect(find.text('Connectez-vous à Makolo'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}

class _HandoffPersonalRepository extends PersonalRepository {
  _HandoffPersonalRepository() : super(_NeverUsedStore());

  @override
  Stream<StoredProjection?> watchNow() => Stream.value(
    StoredProjection(
      kind: 'personal.now',
      schemaVersion: 1,
      payload: const {
        'surface': 'now_me',
        'selection': {'state': 'empty'},
        'actor_attention_state': 'calm',
        'freshness': {'state': 'fresh'},
        'items': [],
        'continuation': null,
        'terminal': {'state': 'empty'},
      },
      receivedAt: DateTime.utc(2026, 10, 8),
    ),
  );

  @override
  Stream<OwnerSourceState> watchNowSource() =>
      Stream.value(OwnerSourceState.unknown);

  @override
  Stream<StoredProjection?> watchMe() => Stream.value(
    StoredProjection(
      kind: 'personal.me',
      schemaVersion: 1,
      payload: const {
        'identity': {
          'username': 'amina',
          'display_name': '@amina',
          'activation': {'percentage': 33, 'is_complete': false},
        },
      },
      receivedAt: DateTime.utc(2026, 10, 8),
    ),
  );
}

class _NeverUsedStore implements ProfileStore {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
