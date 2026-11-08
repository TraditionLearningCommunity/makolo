import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/features/settings/subscription_actions_panel.dart';
import 'package:makolo_mobile/features/settings/subscription_billing_format.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets(
    'server catalog terms remain distinct from absent billing terms',
    (tester) async {
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SubscriptionActionsPanel(
              runtime: runtime,
              section: 'plans',
              snapshot: {
                'subscription': {
                  'id': 'owned',
                  'current_base': {'name': 'Formule gratuite'},
                  'active_addons': <Object>[],
                },
                'catalog': [
                  {
                    'name': 'Formule gratuite',
                    'plan_version_id': 'plan-free',
                    'current': true,
                    'can_request': false,
                    'billing_terms': {
                      'amount': '0.00',
                      'currency': 'USD',
                      'period_unit': 'month',
                      'period_count': 1,
                    },
                  },
                  {
                    'name': 'Formule sans tarif publié',
                    'plan_version_id': 'plan-unknown',
                    'current': false,
                    'can_request': true,
                    'billing_terms': null,
                  },
                ],
                'billing': {'items': <Object>[], 'next_offset': null},
              },
              onUpdated: () async {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        subscriptionPriceLabel({'amount': '0.00', 'currency': 'USD'}),
        'Gratuit',
      );
      expect(find.text('Formule actuelle : Formule gratuite'), findsOneWidget);
      expect(find.text('Tarif non communiqué'), findsOneWidget);
      expect(find.text('Voir les détails'), findsOneWidget);

      await tester.tap(find.text('Voir les détails'));
      await tester.pump();
      expect(
        find.text('Cette action nécessite une connexion active.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('a server-empty catalog does not invent paid features', (
    tester,
  ) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubscriptionActionsPanel(
            runtime: runtime,
            section: 'plans',
            snapshot: const {
              'subscription': {'id': 'owned', 'active_addons': <Object>[]},
              'catalog': <Object>[],
              'billing': {'items': <Object>[], 'next_offset': null},
            },
            onUpdated: () async {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('Aucune autre offre disponible pour le moment.'),
      findsOneWidget,
    );
    expect(find.text('Voir les détails'), findsNothing);
  });

  testWidgets('paid offer opens the exact server-provided payment obligation', (
    tester,
  ) async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'test-profile',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    var posts = 0;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        if (request.data == null) {
          return MockResponse(
            jsonEncode({
              'target_name': 'Formule Max',
              'current_name': 'Formule Plus',
              'billing_terms': {
                'amount': '18.00',
                'currency': 'USD',
                'period_unit': 'month',
                'period_count': 1,
              },
              'can_confirm': true,
              'features_gained': <Object>[],
              'features_lost': <Object>[],
              'quota_changes': <Object>[],
            }),
            200,
          );
        }
        posts++;
        return MockResponse(
          jsonEncode({
            'transition': {
              'id': 'transition-1',
              'open': true,
              'next_action': 'pay',
              'payment_obligation_id': 'obligation-from-server',
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
    );
    addTearDown(runtime.close);
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => Scaffold(
            body: SubscriptionActionsPanel(
              runtime: runtime,
              section: 'plans',
              snapshot: {
                'subscription': {
                  'id': 'owned',
                  'can_manage': true,
                  'active_addons': <Object>[],
                },
                'catalog': [
                  {
                    'plan_type': 'base',
                    'plan_version_id': 'plan-max',
                    'name': 'Formule Max',
                    'current': false,
                    'can_request': true,
                    'billing_terms': {
                      'amount': '18.00',
                      'currency': 'USD',
                      'period_unit': 'month',
                    },
                  },
                ],
                'billing': {'items': <Object>[], 'next_offset': null},
              },
              onUpdated: () async {},
            ),
          ),
        ),
        GoRoute(
          path: '/payments/obligations/:id',
          builder: (context, state) =>
              Scaffold(body: Text('Paiement ${state.pathParameters['id']!}')),
        ),
      ],
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Voir les détails'));
    await tester.pumpAndSettle();
    expect(find.text('Continuer vers le paiement'), findsOneWidget);
    await tester.tap(find.text('Continuer vers le paiement'));
    await tester.pumpAndSettle();
    expect(posts, 0);
    expect(find.text('Confirmer le changement ?'), findsOneWidget);
    await tester.tap(find.text('Confirmer').last);
    await tester.pumpAndSettle();
    expect(find.text('Paiement obligation-from-server'), findsOneWidget);
    expect(posts, 1);
  });
}
