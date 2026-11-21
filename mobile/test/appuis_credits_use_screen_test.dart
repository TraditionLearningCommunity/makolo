import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/appuis_credits_use_screen.dart';

Map<String, dynamic> projection({
  int credits = 240,
  int pending = 35,
  Map<String, dynamic>? money,
  List<Map<String, dynamic>> rewards = const [],
}) {
  final data = <String, dynamic>{
    'summary': {'available_credits': credits, 'pending_credits': pending},
    'account': {'points_balance': credits, 'pending_points': pending},
    'rewards': rewards,
  };
  if (money != null) {
    data['monetary_equivalent'] = money;
  }
  return data;
}

Map<String, dynamic> featureReward({String id = 'feature-1', int cost = 80}) =>
    {
      'id': id,
      'kind': 'entitlement',
      'name': 'Fonctionnalité utile',
      'points_cost': cost,
      'self_eligible': true,
      'capabilities': ['redeem'],
      'links': {'redeem': '/api/v1/recognition/rewards/$id/redeem/'},
      'presentation': {
        'category': 'feature',
        'action': 'Débloquer',
        'duration_days': 30,
      },
    };

Widget harness(
  Map<String, dynamic> data, {
  bool space = false,
  bool canSpend = true,
  bool Function(Map<String, dynamic>)? canUseReward,
  Future<Map<String, dynamic>?> Function(Map<String, dynamic>)? onRedeem,
  Future<Map<String, dynamic>?> Function()? onReload,
  Listenable? actorChanges,
  bool Function()? actorIsCurrent,
}) => MaterialApp(
  home: AppuisCreditsUseScreen(
    initial: data,
    refreshOnOpen: false,
    space: space,
    canSpend: () => canSpend,
    canUseReward: canUseReward ?? (_) => true,
    onRedeem: onRedeem ?? (reward) async => null,
    onReload: onReload ?? () async => data,
    actorChanges: actorChanges,
    actorIsCurrent: actorIsCurrent,
  ),
);

void main() {
  testWidgets('the single page shows credits and configured monetary value', (
    tester,
  ) async {
    await tester.pumpWidget(
      harness(projection(money: {'amount': '12.00', 'currency': 'USD'})),
    );
    expect(find.text('Utiliser mes crédits'), findsOneWidget);
    expect(find.text('240 crédits'), findsOneWidget);
    expect(find.text('12.00 USD'), findsOneWidget);
    expect(find.text('Retirer'), findsOneWidget);
    final button = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Retirer'),
    );
    expect(button.onPressed, isNull);
    expect(find.text('35 crédits en attente'), findsNothing);
    expect(find.text('Abonnements'), findsNothing);
    expect(find.text('Fonctionnalités'), findsNothing);
  });

  testWidgets('unconfigured equivalence is wholly absent', (tester) async {
    await tester.pumpWidget(harness(projection()));
    expect(find.text('Retirer'), findsNothing);
    expect(find.text('Valeur en argent'), findsNothing);
    expect(find.text('12.00 USD'), findsNothing);
    expect(find.text('Abonnements'), findsNothing);
  });

  testWidgets(
    'each real feature is directly actionable with one confirmation',
    (tester) async {
      var calls = 0;
      await tester.pumpWidget(
        harness(
          projection(rewards: [featureReward()]),
          onRedeem: (reward) async {
            calls++;
            return {'status': 'fulfilled', 'points_cost': 80};
          },
          onReload: () async =>
              projection(credits: 160, pending: 35, rewards: []),
        ),
      );
      expect(find.text('Fonctionnalités'), findsOneWidget);
      expect(find.text('Fonctionnalité utile'), findsOneWidget);
      expect(find.text('30 jours'), findsOneWidget);
      await tester.tap(find.text('Débloquer'));
      await tester.pumpAndSettle();
      expect(calls, 0);
      expect(find.text('Confirmer'), findsOneWidget);
      await tester.tap(find.text('Confirmer'));
      await tester.pumpAndSettle();
      expect(calls, 1);
      expect(find.text('160 crédits'), findsOneWidget);
      expect(find.text('Fonctionnalité utile'), findsNothing);
    },
  );

  testWidgets('canceling does not invoke the owner', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      harness(
        projection(rewards: [featureReward()]),
        onRedeem: (_) async {
          calls++;
          return {'status': 'fulfilled'};
        },
      ),
    );
    await tester.tap(find.text('Débloquer'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Annuler'));
    await tester.pumpAndSettle();
    expect(calls, 0);
    expect(find.text('240 crédits'), findsOneWidget);
  });

  testWidgets('Space without spending authority sees disabled actions', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      harness(
        projection(rewards: [featureReward()]),
        space: true,
        canSpend: false,
        onRedeem: (_) async {
          calls++;
          return {'status': 'fulfilled'};
        },
      ),
    );
    expect(find.text('Utiliser nos crédits'), findsOneWidget);
    final unlock = tester.widget<TextButton>(
      find.widgetWithText(TextButton, 'Débloquer'),
    );
    expect(unlock.onPressed, isNull);
    expect(calls, 0);
  });

  testWidgets('refused or uncertain action preserves the known credits', (
    tester,
  ) async {
    await tester.pumpWidget(
      harness(
        projection(rewards: [featureReward()]),
        onRedeem: (_) async => null,
      ),
    );
    await tester.tap(find.text('Débloquer'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirmer'));
    await tester.pumpAndSettle();
    expect(find.text('240 crédits'), findsOneWidget);
    expect(find.text('Avantage activé.'), findsNothing);
  });

  testWidgets('no second spend against stale amount after confirmed action', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      harness(
        projection(rewards: [featureReward()]),
        onRedeem: (_) async {
          calls++;
          return {'status': 'requested'};
        },
        onReload: () async => null,
      ),
    );
    await tester.tap(find.text('Débloquer'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirmer'));
    await tester.pumpAndSettle();
    expect(calls, 1);
    expect(find.text('Crédits à confirmer'), findsOneWidget);
    final unlock = tester.widget<TextButton>(
      find.widgetWithText(TextButton, 'Débloquer'),
    );
    expect(unlock.onPressed, isNull);
  });
  testWidgets('switching Profile or Space closes the private spending page', (
    tester,
  ) async {
    final current = ValueNotifier<bool>(true);
    await tester.pumpWidget(
      harness(
        projection(rewards: [featureReward()]),
        actorChanges: current,
        actorIsCurrent: () => current.value,
      ),
    );
    expect(find.text('240 crédits'), findsOneWidget);
    current.value = false;
    await tester.pumpAndSettle();
    expect(find.text('240 crédits'), findsNothing);
    current.dispose();
  });

  testWidgets(
    'fresh owner confirmation is required before showing cash value',
    (tester) async {
      final fresh = Completer<Map<String, dynamic>?>();
      final initial = projection(money: {'amount': '12.00', 'currency': 'USD'});
      await tester.pumpWidget(
        MaterialApp(
          home: AppuisCreditsUseScreen(
            initial: initial,
            space: false,
            canSpend: () => true,
            canUseReward: (_) => false,
            onRedeem: (_) async => null,
            onReload: () => fresh.future,
          ),
        ),
      );
      expect(find.text('12.00 USD'), findsNothing);
      expect(find.text('Retirer'), findsNothing);
      fresh.complete(initial);
      await tester.pumpAndSettle();
      expect(find.text('12.00 USD'), findsOneWidget);
      expect(find.text('Retirer'), findsOneWidget);
    },
  );

  testWidgets('pending credits cannot pay for a reward', (tester) async {
    await tester.pumpWidget(
      harness(
        projection(credits: 0, pending: 35, rewards: [featureReward(cost: 20)]),
      ),
    );
    expect(find.text('0 crédits'), findsOneWidget);
    final action = tester.widget<TextButton>(
      find.widgetWithText(TextButton, 'Débloquer'),
    );
    expect(action.onPressed, isNull);
    expect(find.text('35 crédits'), findsNothing);
  });
}
