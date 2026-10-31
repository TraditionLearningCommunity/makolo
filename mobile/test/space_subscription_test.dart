import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/settings/billing_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  ActorContext current = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String profileId) async => current;

  @override
  Future<void> writeActorContext(String profileId, ActorContext context) async {
    current = context;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    current = const PersonalActorContext();
  }
}

void main() {
  testWidgets('Space subscription uses Space snapshot and clears it on actor switch', (
    tester,
  ) async {
    final actors = await ActorContextController.restore(
      profileId: 'profile-a',
      store: _ActorStore(),
    );
    await actors.selectSpace(SpaceActorIdentity(id: 'space-a', slug: 'space-a'));
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-a', accessToken: 'access', refreshToken: 'refresh',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        expect(request.url.path, '/api/v1/subscriptions/spaces/space-a/');
        return MockResponse(jsonEncode({
          'space': {'id': 'space-a', 'slug': 'space-a', 'name': 'Espace A'},
          'subscription': {
            'id': 'sub-a', 'subject_type': 'space',
            'can_manage': true,
            'status': {'label': 'Actif', 'explanation': 'Capacités collectives'},
            'current_base': {'name': 'Formule de l’Espace A'},
            'active_addons': [],
          },
          'capabilities': [
            {
              'name': 'Équipe de l’Espace', 'value': 10,
              'value_label': '10 membres', 'usage': 4,
              'usage_label': '4 utilisés sur 10', 'allowed': true,
              'over_limit': false,
            },
          ],
          'catalog': [],
          'history': {'items': [], 'next_offset': null},
          'billing': {'items': [], 'next_offset': null},
        }), 200);
      }).dio,
    );
    final runtime = AppRuntime(
      tokens: tokens, session: null,
      recovery: SessionRecoveryController(),
      actorContext: actors, api: api,
    );
    addTearDown(runtime.close);
    await tester.pumpWidget(MaterialApp(
      home: BillingScreen(
        runtime: runtime, spaceSlug: 'space-a', expectedSpaceId: 'space-a',
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Formule de l’Espace A'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Équipe de l’Espace'), 180);
    expect(find.text('Équipe de l’Espace'), findsOneWidget);
    expect(find.text('Mon abonnement'), findsNothing);

    await actors.selectSpace(SpaceActorIdentity(id: 'space-b', slug: 'space-b'));
    await tester.pumpAndSettle();
    expect(find.text('Formule de l’Espace A'), findsNothing);
    expect(find.textContaining('Sélectionnez cet Espace'), findsOneWidget);
  });

  testWidgets('Space view-only can preview but never confirm a change', (
    tester,
  ) async {
    final actors = await ActorContextController.restore(
      profileId: 'profile-a', store: _ActorStore(),
    );
    await actors.selectSpace(SpaceActorIdentity(id: 'space-a', slug: 'space-a'));
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-a', accessToken: 'access', refreshToken: 'refresh',
      ),
    );
    var posts = 0;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        if (request.url.path == '/api/v1/subscriptions/spaces/space-a/') {
          return MockResponse(jsonEncode({
            'space': {'id': 'space-a', 'slug': 'space-a', 'name': 'Espace A'},
            'subscription': {
              'id': 'sub-a', 'subject_type': 'space',
              'can_manage': false,
              'status': {'label': 'Actif'},
              'current_base': {'name': 'Base Espace'},
              'active_addons': [],
            },
            'catalog': [
              {
                'name': 'Alternative Espace',
                'plan_version_id': 'plan-a', 'plan_type': 'base',
                'can_request': false, 'can_preview': true,
                'current': false, 'eligibility_label': 'Disponible',
              },
            ],
            'history': {'items': [], 'next_offset': null},
            'billing': {'items': [], 'next_offset': null},
          }), 200);
        }
        if (request.url.path ==
            '/api/v1/subscriptions/spaces/space-a/plans/plan-a/') {
          if (request.url.path == '/api/v1/subscriptions/spaces/space-a/plans/plan-a/' &&
              request.body.isNotEmpty) {
            posts++;
          }
          return MockResponse(jsonEncode({
            'target_name': 'Alternative Espace', 'kind': 'base_switch',
            'can_confirm': false, 'features_gained': [],
            'features_lost': [], 'requirements': [], 'quota_changes': [],
          }), 200);
        }
        throw StateError('Unexpected endpoint: ${request.url.path}');
      }).dio,
    );
    final runtime = AppRuntime(
      tokens: tokens, session: null, recovery: SessionRecoveryController(),
      actorContext: actors, api: api,
    );
    addTearDown(runtime.close);
    await tester.pumpWidget(MaterialApp(
      home: BillingScreen(
        runtime: runtime, spaceSlug: 'space-a', expectedSpaceId: 'space-a',
      ),
    ));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Examiner le changement'), 180);
    await tester.tap(find.text('Examiner le changement'));
    await tester.pumpAndSettle();
    expect(find.text('Consultation uniquement'), findsOneWidget);
    expect(posts, 0);
  });
}
