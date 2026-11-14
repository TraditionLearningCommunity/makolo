import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/objective_context_banner.dart';

void main() {
  testWidgets(
    'Space presentation displays actual owner, not an assumed actor',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ObjectiveContextBanner(
              payload: {
                'owner': {'kind': 'space', 'label': 'Collectif A'},
                'actor_context': {'kind': 'space'},
              },
            ),
          ),
        ),
      );

      expect(find.text('Espace actif : Collectif A'), findsOneWidget);
      expect(find.textContaining('Porteur : Collectif A'), findsOneWidget);
    },
  );

  testWidgets('Personal lens does not impersonate the Space owner', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ObjectiveContextBanner(
            payload: {
              'owner': {'kind': 'space', 'label': 'Collectif A'},
              'actor_context': {'kind': 'personal'},
            },
          ),
        ),
      ),
    );

    expect(find.text('Consultation depuis mon Profil'), findsOneWidget);
    expect(find.textContaining('Porteur : Collectif A'), findsOneWidget);
  });
}
