import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/appuis_dashboard.dart';

Map<String, dynamic> account(String id, String name, {int points = 0}) => {
  'id': 'account-$id',
  'program': id,
  'program_name': name,
  'organization_name': 'Collectif $id',
  'points_balance': points,
  'points_name': 'points',
};

Map<String, Map<String, dynamic>> data({
  List<Map<String, dynamic>> accounts = const [],
  Map<String, dynamic>? recognition,
  Map<String, dynamic>? partners,
}) => {
  'loyalty': {
    'accounts': accounts,
    'memberships': <Object>[],
    'available_rewards': <Object>[],
    'rewards': <Object>[],
  },
  'recognition': ?recognition,
  'partners': ?partners,
};

Widget harness(
  Map<String, Map<String, dynamic>> snapshots, {
  bool space = false,
  bool canMutate = true,
  Map<String, dynamic>? owner,
  bool Function(Map<String, dynamic>, String, String)? allowed,
  Future<void> Function(Map<String, dynamic>, String, String)? onAction,
}) => MaterialApp(
  home: Scaffold(
    body: SingleChildScrollView(
      child: AppuisDashboard(
        snapshots: snapshots,
        actorKey: space ? 'space:one' : 'personal',
        space: space,
        busy: false,
        onAction: onAction ?? (row, family, action) async {},
        onReadProgram: (id) async => owner,
        onCreateSpaceItem: (owner, action, body) async => false,
        canMutate: canMutate,
        allowed: allowed ?? (row, family, action) => false,
      ),
    ),
  ),
);

void main() {
  test('program identities are grouped, not names or account rows', () {
    final programs = AppuisViewData.programs({
      'accounts': [
        account('one', 'Club'),
        account('one', 'Club'),
        account('two', 'Club'),
      ],
      'memberships': [
        {'program': 'one', 'status': 'active'},
      ],
      'available_rewards': [
        {'program': 'one', 'name': 'Avantage'},
      ],
    });
    expect(programs, hasLength(2));
    expect(AppuisViewData.programId(programs.first), 'one');
  });

  test('zero balance is not an absence of a program', () {
    final snapshots = data(accounts: [account('one', 'Club', points: 0)]);
    expect(AppuisViewData.available(snapshots, false), ['loyalty']);
    expect(AppuisViewData.positive(0), false);
  });

  test('absent families do not appear as selectable filters', () {
    final snapshots = data(accounts: [account('one', 'Club')]);
    expect(AppuisViewData.available(snapshots, false), ['loyalty']);
    expect(
      AppuisViewData.available({
        'recognition': {
          'account': {'points_balance': 0},
          'summary': {'available_credits': 0},
          'achievements': <Object>[],
          'rewards': <Object>[],
        },
      }, false),
      isEmpty,
    );
  });

  testWidgets('the root presents compact programs without zero points', (
    tester,
  ) async {
    await tester.pumpWidget(
      harness(
        data(
          accounts: [
            account('one', 'Club A'),
            account('two', 'Club B', points: 7),
          ],
        ),
      ),
    );
    expect(find.text('Club A'), findsOneWidget);
    expect(find.text('Club B'), findsOneWidget);
    expect(find.textContaining('0 points'), findsNothing);
    expect(find.textContaining('7 points'), findsOneWidget);
    expect(find.byType(ChoiceChip), findsNothing);
  });

  testWidgets('three previews and a working full collection', (tester) async {
    await tester.pumpWidget(
      harness(
        data(
          accounts: [
            account('one', 'Club A'),
            account('two', 'Club B'),
            account('three', 'Club C'),
            account('four', 'Club D'),
          ],
        ),
      ),
    );
    expect(find.text('Club D'), findsNothing);
    await tester.tap(find.text('Tout voir'));
    await tester.pumpAndSettle();
    expect(find.text('Club D'), findsOneWidget);
  });

  testWidgets('local filters show only owner families', (tester) async {
    await tester.pumpWidget(
      harness(
        data(
          accounts: [account('one', 'Club A')],
          recognition: {
            'summary': {'available_credits': 2},
            'rewards': [
              {'id': 'reward', 'name': 'Récompense A'},
            ],
          },
        ),
      ),
    );
    expect(find.byType(ChoiceChip), findsNWidgets(3));
    await tester.tap(find.text('Fidélité'));
    await tester.pumpAndSettle();
    expect(find.text('Club A'), findsOneWidget);
    expect(find.text('Récompense A'), findsNothing);
  });

  testWidgets('Space reuses the same presentation without personal programs', (
    tester,
  ) async {
    await tester.pumpWidget(
      harness({
        'loyalty': {
          'program': {'id': 'one', 'name': 'Club collectif'},
        },
      }, space: true),
    );
    expect(find.text('Notre fidélité'), findsOneWidget);
    expect(find.text('Club collectif'), findsOneWidget);
    expect(find.text('Ma fidélité'), findsNothing);
  });

  testWidgets('single indicator uses a compact banner', (tester) async {
    await tester.pumpWidget(
      harness(data(accounts: [account('one', 'Club A')])),
    );
    expect(find.text('1 programme'), findsOneWidget);
    expect(find.text('Ce qui est déjà disponible'), findsNothing);
  });

  testWidgets('true empty has no summary, filters or fictional items', (
    tester,
  ) async {
    await tester.pumpWidget(harness(data()));
    expect(find.text('Mes appuis'), findsNothing);
    expect(find.byType(ChoiceChip), findsNothing);
    expect(find.textContaining('programme'), findsNothing);
  });

  testWidgets('Space detail exposes real levels and plan benefits', (
    tester,
  ) async {
    const program = {
      'id': 'space-program',
      'name': 'Parcours fidélité communautaire',
      'description': 'Programme de reconnaissance des participations',
      'tiers': [
        {
          'name': 'Niveau START',
          'threshold_points': 0,
          'benefits': 'Accueil du participant',
          'is_active': true,
        },
        {
          'name': 'Niveau ACTIF',
          'threshold_points': 50,
          'benefits': 'Accès aux avantages',
          'is_active': true,
        },
      ],
      'membership_plans': [
        {
          'name': 'Adhésion fictive gratuite',
          'id': 'plan',
          'is_active': true,
          'is_free': true,
          'duration_days': 365,
          'benefits': 'Participer au programme',
        },
      ],
      'rewards': <Object>[],
    };
    await tester.pumpWidget(
      harness(
        {
          'loyalty': {'program': program},
        },
        space: true,
        owner: {'program': program, 'capabilities': <Object>[]},
      ),
    );
    await tester.tap(find.text('Parcours fidélité communautaire').last);
    await tester.pumpAndSettle();
    expect(find.text('Niveau START'), findsOneWidget);
    expect(find.text('Dès 50 points · Accès aux avantages'), findsOneWidget);
    expect(find.textContaining('Participer au programme'), findsOneWidget);
    expect(find.text('Ajouter'), findsNothing);
  });

  testWidgets('membership detail makes cancellation secondary', (tester) async {
    final membership = <String, dynamic>{
      'id': 'mem-1',
      'program': 'one',
      'plan': 'p1',
      'plan_name': 'Formule gratuite',
      'status': 'active',
      'capabilities': ['cancel'],
      'links': {'cancel': '/api/v1/loyalty/memberships/mem-1/cancel/'},
    };
    await tester.pumpWidget(
      harness(
        {
          'loyalty': {
            'accounts': [account('one', 'Club A')],
            'memberships': [membership],
          },
        },
        owner: {
          'program': {
            'id': 'one',
            'name': 'Club A',
            'membership_plans': [
              {
                'id': 'p1',
                'name': 'Formule gratuite',
                'benefits': 'Accès aux ateliers',
                'is_active': true,
              },
            ],
          },
        },
        allowed: (row, family, action) => action == 'cancel',
      ),
    );
    await tester.tap(find.text('Club A').first);
    await tester.pumpAndSettle();
    expect(find.text('Mettre fin à cette adhésion'), findsNothing);
    await tester.tap(find.text('Formule gratuite').first);
    await tester.pumpAndSettle();
    expect(find.text('Accès aux ateliers'), findsOneWidget);
    expect(find.text('Mettre fin à cette adhésion'), findsOneWidget);
  });

  testWidgets('a refused action or offline depth exposes no fake success', (
    tester,
  ) async {
    final membership = <String, dynamic>{
      'id': 'mem-1',
      'program': 'one',
      'plan_name': 'Formule gratuite',
      'status': 'active',
      'capabilities': ['cancel'],
    };
    var called = false;
    await tester.pumpWidget(
      harness(
        {
          'loyalty': {
            'accounts': [account('one', 'Club A')],
            'memberships': [membership],
          },
        },
        canMutate: false,
        allowed: (_, _, _) => false,
        onAction: (_, _, _) async {
          called = true;
        },
      ),
    );
    await tester.tap(find.text('Club A').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Formule gratuite'));
    await tester.pumpAndSettle();
    expect(find.text('Mettre fin à cette adhésion'), findsNothing);
    expect(called, false);
  });
  testWidgets('local content remains usable during a silent network pause',
      (tester) async {
    final local = data(accounts: [account('one', 'Club A')]);
    await tester.pumpWidget(harness(local, canMutate: false));
    expect(find.text('Club A'), findsOneWidget);
    expect(find.textContaining('Actualisation impossible'), findsNothing);
    await tester.pumpWidget(harness(data(
      accounts: [account('one', 'Club A')],
      recognition: {
        'summary': {'available_credits': 1},
        'rewards': [{'id': 'reward-1', 'name': 'Récompense'}],
      },
    ), canMutate: true));
    await tester.pumpAndSettle();
    expect(find.byType(ChoiceChip), findsNWidgets(3));
    expect(find.text('Club A'), findsOneWidget);
    expect(find.text('Récompense'), findsWidgets);
  });

}
