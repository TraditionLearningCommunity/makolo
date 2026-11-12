import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/project_description.dart';

void main() {
  Widget harness(String? text) => MaterialApp(
    home: Scaffold(
      body: SizedBox(
        width: 320,
        child: ProjectDescription(description: text),
      ),
    ),
  );

  testWidgets('short Project description has no disclosure control', (
    tester,
  ) async {
    await tester.pumpWidget(harness('Un horizon concret.'));
    expect(find.text('Un horizon concret.'), findsOneWidget);
    expect(find.byTooltip('Lire toutes les informations'), findsNothing);
    expect(find.text('Informations du Projet'), findsNothing);
  });

  testWidgets('empty description disappears instead of inventing a label', (
    tester,
  ) async {
    await tester.pumpWidget(harness('  '));
    expect(find.byIcon(Icons.info_outline_rounded), findsNothing);
    expect(find.byType(IconButton), findsNothing);
  });

  testWidgets('long description expands and can be folded again', (
    tester,
  ) async {
    final longText = List.filled(
      20,
      'Une initiative qui relie les résultats et les personnes.',
    ).join(' ');
    await tester.pumpWidget(harness(longText));

    final description = find.text(longText);
    expect(description, findsOneWidget);
    expect(tester.widget<Text>(description).maxLines, 3);
    expect(find.byTooltip('Lire toutes les informations'), findsOneWidget);

    await tester.tap(find.byTooltip('Lire toutes les informations'));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(description).maxLines, isNull);
    expect(find.byTooltip('Replier les informations'), findsOneWidget);

    await tester.tap(find.byTooltip('Replier les informations'));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(description).maxLines, 3);
  });

  testWidgets('new description resets the expanded state', (tester) async {
    final first = List.filled(20, 'Premier horizon durable.').join(' ');
    final second = List.filled(20, 'Nouvel horizon collectif.').join(' ');
    Widget build(String text) => MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: 320,
          child: ProjectDescription(description: text),
        ),
      ),
    );

    await tester.pumpWidget(build(first));
    await tester.tap(find.byTooltip('Lire toutes les informations'));
    await tester.pumpAndSettle();

    await tester.pumpWidget(build(second));
    final next = find.text(second);
    expect(tester.widget<Text>(next).maxLines, 3);
  });
}
