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
import 'package:makolo_mobile/network/api_error.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  ActorContext value = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String profileId) async => value;

  @override
  Future<void> writeActorContext(String profileId, ActorContext context) async {
    value = context;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    value = const PersonalActorContext();
  }
}

void main() {
  test('only typed Subscription validation carries a team quota handoff', () {
    final quota = MakoloApiError.fromResponse(
      400,
      '{"subscription":["La capacité de membres actifs est atteinte."]}',
    );
    expect(quota.statusCode, 400);
    expect(quota.fields.containsKey('subscription'), isTrue);

    final authority = MakoloApiError.fromResponse(
      403,
      '{"detail":"Autorité absente."}',
    );
    expect(authority.fields.containsKey('subscription'), isFalse);

    final other = MakoloApiError.fromResponse(
      400,
      '{"email":["Profil introuvable."]}',
    );
    expect(other.fields.containsKey('subscription'), isFalse);
  });

  testWidgets(
    'Space Subscription is scoped, read-only and never uses Profile billing',
    (tester) async {
      final actor = await ActorContextController.restore(
        profileId: 'profile-a',
        store: _ActorStore(),
      );
      await actor.selectSpace(
        SpaceActorIdentity(id: 'space-a', slug: 'space-a'),
      );
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          profileId: 'profile-a',
          accessToken: 'access',
          refreshToken: 'refresh',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          expect(request.url.path, '/api/v1/subscriptions/spaces/space-a/');
          return MockResponse(
            jsonEncode({
              'space': {'id': 'space-a', 'slug': 'space-a', 'name': 'Espace A'},
              'subscription': {
                'id': 'space-subscription-a',
                'subject_type': 'space',
                'can_manage': false,
                'status': {'label': 'Actif', 'explanation': 'Valide'},
                'current_base': {'name': 'BASE de l’Espace A'},
                'active_addons': [],
              },
              'capabilities': [],
              'catalog': [
                {
                  'name': 'Formule collective',
                  'plan_version_id': '1c8bef72-1d66-4c12-b87f-5ccff530de46',
                  'plan_type': 'base',
                  'can_preview': true,
                  'can_request': false,
                  'billing_terms': null,
                },
              ],
              'history': {'items': [], 'next_offset': null},
              'billing': {
                'items': [],
                'next_offset': null,
                'visibility': 'restricted',
              },
            }),
            200,
          );
        }).dio,
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: null,
        recovery: SessionRecoveryController(),
        api: api,
        actorContext: actor,
      );
      addTearDown(runtime.close);
      await tester.pumpWidget(
        MaterialApp(
          home: BillingScreen(
            runtime: runtime,
            spaceSlug: 'space-a',
            expectedSpaceId: 'space-a',
            fromTeam: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Revenir à l’équipe'), findsOneWidget);
      expect(find.text('BASE de l’Espace A'), findsOneWidget);
      expect(find.text('Abonnement de l’Espace'), findsWidgets);
      expect(find.text('Formule collective'), findsNothing);
      await tester.ensureVisible(find.text('Changer de formule'));
      await tester.tap(find.text('Changer de formule'));
      await tester.pumpAndSettle();
      expect(find.text('Formule collective'), findsOneWidget);
      expect(find.text('Voir les détails'), findsOneWidget);
      expect(find.text('Facturation de mon abonnement'), findsNothing);
      expect(find.text('Confirmer'), findsNothing);

      await actor.selectPersonal();
      await tester.pumpAndSettle();
      expect(find.text('BASE de l’Espace A'), findsNothing);
      expect(find.text('Revenir à l’équipe'), findsNothing);
      expect(find.textContaining('Sélectionnez cet Espace'), findsWidgets);
    },
  );

  testWidgets('Space Subscription rejects a mismatched server subject', (
    tester,
  ) async {
    final actor = await ActorContextController.restore(
      profileId: 'profile-a',
      store: _ActorStore(),
    );
    await actor.selectSpace(SpaceActorIdentity(id: 'space-a', slug: 'space-a'));
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-a',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient(
        (request) async => MockResponse(
          jsonEncode({
            'space': {'id': 'space-b', 'slug': 'space-b'},
            'subscription': {
              'subject_type': 'space',
              'current_base': {'name': 'BASE d’un autre Espace'},
            },
          }),
          200,
        ),
      ).dio,
    );
    final runtime = AppRuntime(
      tokens: tokens,
      session: null,
      recovery: SessionRecoveryController(),
      api: api,
      actorContext: actor,
    );
    addTearDown(runtime.close);
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          runtime: runtime,
          spaceSlug: 'space-a',
          expectedSpaceId: 'space-a',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('BASE d’un autre Espace'), findsNothing);
    expect(find.textContaining('Impossible de vérifier'), findsOneWidget);
  });
}
