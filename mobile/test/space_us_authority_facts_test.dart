import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/space/space_us_authority_facts.dart';

void main() {
  testWidgets('Missing authority data does not mean no active mandates', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SpaceUsAuthorityFacts(payload: {}),
        ),
      ),
    );
    expect(find.text('Autorisations indisponibles.'), findsOneWidget);
    expect(find.text('Aucune autorisation active.'), findsNothing);
  });

  testWidgets('N3 shows role, scope and rights without exposing codes', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: SpaceUsAuthorityFacts(
              payload: {
                'mandates': [
                  {
                    'role': {
                      'code': 'internal_role',
                      'label': 'Responsable financier',
                    },
                    'scope': {
                      'kind': 'activity',
                      'label': 'Activité',
                      'target': 'Départ Lubumbashi',
                    },
                    'valid_until': '2026-12-01T10:00:00Z',
                    'permissions': [
                      {
                        'code': 'finance.view',
                        'label': 'Consulter les montants',
                      },
                    ],
                  },
                ],
              },
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Responsable financier'), findsOneWidget);
    expect(find.text('Activité · Départ Lubumbashi'), findsOneWidget);
    expect(find.text('Droits associés à ce rôle'), findsOneWidget);
    expect(find.text('Consulter les montants'), findsOneWidget);
    expect(find.textContaining('Fin de validité'), findsOneWidget);
    expect(find.textContaining('internal_role'), findsNothing);
    expect(find.textContaining('finance.view'), findsNothing);
  });

  testWidgets('N3 does not invent rights when none are current', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: SpaceUsAuthorityFacts(payload: {'mandates': []})),
      ),
    );
    expect(find.text('Aucune autorisation active.'), findsOneWidget);
  });
}
