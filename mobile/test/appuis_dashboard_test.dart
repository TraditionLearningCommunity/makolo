import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/appuis_dashboard.dart';

Map<String, dynamic> account(String id, String name, {int points = 0}) => {
  'id': 'account-' + id,
  'program': id,
  'program_name': name,
  'organization_name': 'Collectif ' + id,
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
  if (recognition != null) 'recognition': recognition,
  if (partners != null) 'partners': partners,
};

Widget harness(
  Map<String, Map<String, dynamic>> snapshots, {
  bool space = false,
}) => MaterialApp(
  home: Scaffold(
    body: SingleChildScrollView(
      child: AppuisDashboard(
        snapshots: snapshots,
        actorKey: space ? 'space:one' : 'personal',
        space: space,
        busy: false,
        onAction: (row, family, action) async {},
        allowed: (row, family, action) => false,
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
}
