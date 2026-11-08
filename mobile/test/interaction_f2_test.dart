import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/interaction_f2.dart';
import 'package:makolo_mobile/design/interaction_primitives.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  test('F2 selection and local query stay within supplied identities', () {
    final controller = MakoloSelectionController();
    controller.toggle('a');
    controller.toggle('b');
    controller.retainVisible(['b']);
    expect(controller.selectedIds, {'b'});
    controller.clear();
    expect(controller.count, 0);
    controller.dispose();
    final records = [
      (label: 'Service Matadi', category: 'transport'),
      (label: 'Atelier Kinshasa', category: 'formation'),
      (label: 'Service Goma', category: 'transport'),
    ];
    expect(
      makoloFilterLocal(
        records,
        query: 'service',
        textOf: (item) => item.label,
        category: 'transport',
        categoryOf: (item) => item.category,
      ).map((item) => item.label).toList(),
      ['Service Matadi', 'Service Goma'],
    );
    expect(
      makoloFilterLocal(
        ['Dossier Matadi', 'Projet Goma', 'Dossier Kinshasa'],
        query: 'Dossier',
        textOf: (item) => item,
      ),
      ['Dossier Matadi', 'Dossier Kinshasa'],
    );
  });

  testWidgets('F2 search emits local criteria, not a global query', (
    tester,
  ) async {
    String? query;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloSortFilterBar(
            query: '',
            onQueryChanged: (value) => query = value,
          ),
        ),
      ),
    );
    await tester.enterText(find.byType(TextField), 'Matadi');
    expect(query, 'Matadi');
  });

  testWidgets('F2 preview reuses bottom sheet', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MakoloContextPreviewButton(
            builder: (_) => const Text('Contexte consultable'),
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Aperçu'));
    await tester.pumpAndSettle();
    expect(find.text('Contexte consultable'), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Contexte consultable'), findsNothing);
  });

  testWidgets('F2 editor waits for canonical owner result', (tester) async {
    final pending = Completer<MakoloInlineSaveResult>();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloInlineEditor(
            value: 'Titre initial',
            onSave: (_) => pending.future,
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Modifier'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Brouillon');
    await tester.tap(find.text('Enregistrer'));
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    pending.complete(const MakoloInlineSaveResult.confirmed('Titre confirmé'));
    await tester.pumpAndSettle();
    expect(find.text('Titre confirmé'), findsOneWidget);
  });

  testWidgets('F2 edit refusal preserves draft and supports cancellation', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloInlineEditor(
            value: 'Titre stable',
            onSave: (_) async => const MakoloInlineSaveResult.conflict(),
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Modifier'));
    await tester.enterText(find.byType(TextField), 'Autre titre');
    await tester.tap(find.text('Enregistrer'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Ce contenu a changé'), findsOneWidget);
    await tester.tap(find.text('Annuler'));
    await tester.pumpAndSettle();
    expect(find.text('Titre stable'), findsOneWidget);
  });

  testWidgets('F2 reorder requests owner and refuses visual fake success', (
    tester,
  ) async {
    final requests = <List<String>>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloOwnerReorderList(
            entries: const [
              MakoloReorderEntry(id: 'a', label: 'Alpha', child: Text('Alpha')),
              MakoloReorderEntry(id: 'b', label: 'Beta', child: Text('Beta')),
            ],
            onRequestReorder: (proposed) async {
              requests.add(proposed);
              return false;
            },
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Descendre Alpha'));
    await tester.pumpAndSettle();
    expect(requests, [
      ['b', 'a'],
    ]);
    expect(find.text('Nouvel ordre non confirmé.'), findsOneWidget);
  });

  testWidgets('F2 move sheet closes only on owner confirmation', (
    tester,
  ) async {
    var accept = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloMoveDestinationButton(
            destinations: const [
              MakoloMoveDestination(id: 'p1', label: 'Projet choisi'),
            ],
            onRequestMove: (_) async => accept,
          ),
        ),
      ),
    );
    await tester.tap(find.text('Déplacer vers…'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Projet choisi'));
    await tester.pumpAndSettle();
    expect(find.text('Déplacement non confirmé.'), findsOneWidget);
    accept = true;
    await tester.tap(find.text('Projet choisi'));
    await tester.pumpAndSettle();
    expect(find.text('Projet choisi'), findsNothing);
  });

  testWidgets('F2 undo is available only with a true owner inverse', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloOwnerUndoButton(
            available: true,
            onRequestUndo: () async {
              calls++;
              return calls == 2;
            },
          ),
        ),
      ),
    );
    await tester.tap(find.text('Annuler cette action'));
    await tester.pumpAndSettle();
    expect(find.text('Annulation non confirmée.'), findsOneWidget);
    await tester.tap(find.text('Annuler cette action'));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.text('Annuler cette action'), findsNothing);
  });

  testWidgets('F2 long-press and visible menu share the same owner action', (
    tester,
  ) async {
    final selected = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloContextActionRow(
            actions: const [
              MakoloInteractionAction(
                id: 'inspect',
                label: 'Inspecter',
                intent: MakoloActionIntent.inspect,
              ),
            ],
            onSelected: (action) => selected.add(action.id),
            child: const Text('Objet'),
          ),
        ),
      ),
    );
    expect(find.byTooltip('Actions'), findsOneWidget);
    await tester.longPress(find.text('Objet'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Inspecter'));
    await tester.pumpAndSettle();
    expect(selected, ['inspect']);
  });
}
