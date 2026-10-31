import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/features/settings/subscription_actions_panel.dart';

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
              snapshot: {
                'subscription': {'id': 'owned', 'active_addons': <Object>[]},
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

      expect(find.text('Gratuit'), findsOneWidget);
      expect(find.text('Tarif non communiqué'), findsOneWidget);
      expect(find.text('Examiner le changement'), findsOneWidget);

      await tester.tap(find.text('Examiner le changement'));
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
      find.text('Aucune autre formule proposée actuellement.'),
      findsOneWidget,
    );
    expect(find.text('Examiner le changement'), findsNothing);
  });
}
