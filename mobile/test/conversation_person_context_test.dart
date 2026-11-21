import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/conversation_point_presentation.dart';

void main() {
  testWidgets('represented Point names the person and shows Space separately', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ConversationPointShell(
            kind: 'information',
            isMine: false,
            authorLabel: 'Patrick',
            representedSpace: true,
            representedSpaceLabel: 'Atelier collectif',
            child: Text('Point validé'),
          ),
        ),
      ),
    );
    expect(find.text('Patrick'), findsOneWidget);
    expect(find.text('Dans le cadre de Atelier collectif'), findsOneWidget);
    expect(find.text('Point validé'), findsOneWidget);
  });

  testWidgets('own represented Point remains attributed to a person', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ConversationPointShell(
            kind: 'information',
            isMine: true,
            authorLabel: 'Amina',
            representedSpace: true,
            representedSpaceLabel: 'Atelier collectif',
            child: Text('Ma contribution'),
          ),
        ),
      ),
    );
    expect(find.text('Vous'), findsOneWidget);
    expect(find.text('Dans le cadre de Atelier collectif'), findsOneWidget);
    expect(find.text('Vous · Atelier collectif'), findsNothing);
  });
}
