import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/objective_workspace_view_switcher.dart';

void main() {
  testWidgets('one accessible icon view control preserves selected mode', (
    tester,
  ) async {
    var selected = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, update) => ObjectiveWorkspaceViewSwitcher<int>(
              selected: selected,
              options: const [
                ObjectiveViewOption(0, Icons.dashboard_outlined, 'Synthèse'),
                ObjectiveViewOption(1, Icons.folder_outlined, 'Dossiers'),
                ObjectiveViewOption(
                  2,
                  Icons.calendar_today_outlined,
                  'Calendrier',
                ),
              ],
              onSelected: (next) => update(() => selected = next),
            ),
          ),
        ),
      ),
    );

    expect(find.byType(IconButton), findsNWidgets(3));
    expect(find.text('Synthèse'), findsNothing);
    expect(find.text('Dossiers'), findsNothing);
    expect(find.byTooltip('Dossiers'), findsOneWidget);

    await tester.tap(find.byTooltip('Dossiers'));
    await tester.pump();
    expect(selected, 1);
  });

  testWidgets('four-view Dossier control fits one row at phone width', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ObjectiveWorkspaceViewSwitcher<int>(
            selected: 0,
            options: const [
              ObjectiveViewOption(0, Icons.dashboard_outlined, 'Synthèse'),
              ObjectiveViewOption(1, Icons.list_rounded, 'Liste'),
              ObjectiveViewOption(
                2,
                Icons.calendar_month_outlined,
                'Chronologie',
              ),
              ObjectiveViewOption(
                3,
                Icons.account_tree_outlined,
                'Dépendances',
              ),
            ],
            onSelected: (_) {},
          ),
        ),
      ),
    );

    expect(find.byType(IconButton), findsNWidgets(4));
    final icons = find.byType(IconButton);
    final tops = [
      for (var index = 0; index < 4; index++)
        tester.getTopLeft(icons.at(index)).dy,
    ];
    expect(tops.toSet().length, 1);
  });
  testWidgets('compact Project selector uses three 44px targets', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ObjectiveWorkspaceViewSwitcher<int>(
            selected: 0,
            compact: true,
            options: const [
              ObjectiveViewOption(0, Icons.dashboard_outlined, 'Synthèse'),
              ObjectiveViewOption(1, Icons.folder_outlined, 'Dossiers'),
              ObjectiveViewOption(2, Icons.calendar_today_outlined, 'Calendrier'),
            ],
            onSelected: (_) {},
          ),
        ),
      ),
    );
    expect(find.byType(IconButton), findsNWidgets(3));
    final buttons = find.byType(IconButton);
    final xs = [
      for (var i = 0; i < 3; i++) tester.getTopLeft(buttons.at(i)).dx,
    ];
    expect(xs[2] - xs[0], lessThanOrEqualTo(92));
    expect(find.byTooltip('Synthèse'), findsOneWidget);
    expect(find.byTooltip('Dossiers'), findsOneWidget);
    expect(find.byTooltip('Calendrier'), findsOneWidget);
  });

}
