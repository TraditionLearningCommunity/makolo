import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/auth/login_screen.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets(
    'successful login invalidates runtime and the authenticated Now renders',
    (tester) async {
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
                  api: api,
                );
              }
              return AppRuntime(
                tokens: tokens,
                session: session,
                recovery: recovery,
                api: api,
                personal: _HandoffPersonalRepository(),
              );
            }),
          ],
          child: const _HandoffHarness(),
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(find.text('Connectez-vous à Makolo'), findsOneWidget);
      await tester.enterText(find.byKey(const Key('login-email')), '@amina');
      await tester.enterText(
        find.byKey(const Key('login-password')),
        'secret-pass',
      );
      final submit = find.byKey(const Key('login-submit'));
      await tester.ensureVisible(submit);
      await tester.pump();
      await tester.tap(submit);

      for (
        var i = 0;
        i < 40 && find.byType(NowScreen).evaluate().isEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 50));
        final error = tester.takeException();
        if (error != null) throw error;
      }

      expect(find.byType(NowScreen), findsOneWidget);
      expect(find.text('Connectez-vous à Makolo'), findsNothing);
      expect((await tokens.readSession())?.profileId, 'profile-a');
      expect(tester.takeException(), isNull);
    },
  );
}

class _HandoffHarness extends ConsumerWidget {
  const _HandoffHarness();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncRuntime = ref.watch(appRuntimeProvider);
    return MaterialApp(
      home: asyncRuntime.when(
        loading: () => const SizedBox.shrink(),
        error: (error, stackTrace) => ErrorWidget(error),
        data: (runtime) {
          if (!runtime.isAuthenticated) {
            return LoginScreen(runtime: runtime);
          }
          final personal = runtime.personal;
          if (personal == null) {
            return const Text('runtime missing personal repository');
          }
          return Scaffold(
            body: NowScreen(
              repository: personal,
              now: () => DateTime.utc(2026, 10, 8),
            ),
          );
        },
      ),
    );
  }
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
}

class _NeverUsedStore implements ProfileStore {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
