import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/space/space_work_surface.dart';

void main() {
  testWidgets('generic work empty state stays honest and calm', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: SpaceWorkSurface(
          payload: {
            'primary_business_label': 'Activités',
            'presentation': {
              'empty_message': 'Aucune activité visible pour le moment.',
            },
            'sections': {
              'preparation': {
                'representation': 'À préparer',
                'role': 'continuity',
                'items': [],
              },
              'activities': {
                'representation': 'Toutes les activités',
                'role': 'structure',
                'items': [],
              },
            },
          },
        ),
      ),
    );
    expect(
      find.text('Aucune activité visible pour le moment.'),
      findsOneWidget,
    );
    expect(find.text('À préparer'), findsNothing);
    expect(find.text('Toutes les activités'), findsNothing);
  });

  testWidgets('generic work renders continuity and structure', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: SpaceWorkSurface(
          payload: {
            'primary_business_label': 'Activités',
            'presentation': {
              'empty_message': 'Aucune activité visible pour le moment.',
            },
            'sections': {
              'upcoming': {
                'representation': 'À venir',
                'role': 'continuity',
                'items': [
                  {
                    'title': 'Atelier demain',
                    'summary': 'Atelier emploi',
                    'timing': {'start_date': '2026-10-09'},
                    'context': {},
                    'source': {'kind': 'occurrence', 'id': 'occ-1'},
                    'capabilities': ['view'],
                  },
                ],
              },
              'activities': {
                'representation': 'Toutes les activités',
                'role': 'structure',
                'items': [
                  {
                    'title': 'Atelier emploi',
                    'timing': {},
                    'context': {},
                    'source': {'kind': 'activity', 'id': 'activity-1'},
                    'capabilities': ['view'],
                  },
                ],
              },
            },
          },
        ),
      ),
    );
    expect(find.text('Activités'), findsOneWidget);
    expect(find.text('À venir'), findsOneWidget);
    expect(find.text('Atelier demain'), findsOneWidget);
    expect(find.text('Toutes les activités'), findsOneWidget);
  });

  testWidgets('transport work keeps structure separate from departures', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: SpaceWorkSurface(
          payload: {
            'primary_business_label': 'Transport',
            'presentation': {'empty_message': 'Aucun transport visible.'},
            'sections': {
              'upcoming': {
                'representation': 'Prochains départs',
                'role': 'continuity',
                'items': [
                  {
                    'title': 'Lubumbashi → Kolwezi',
                    'timing': {'start_date': '2026-10-09'},
                    'context': {},
                    'source': {'kind': 'departure', 'id': 'dep-1'},
                    'capabilities': ['view'],
                  },
                ],
              },
              'routes': {
                'representation': 'Routes',
                'role': 'structure',
                'items': [
                  {
                    'title': 'Route Lubumbashi → Kolwezi',
                    'timing': {},
                    'context': {},
                    'source': {'kind': 'transport_route', 'id': 'route-1'},
                    'capabilities': ['view'],
                  },
                ],
              },
            },
          },
        ),
      ),
    );
    expect(find.text('Transport'), findsOneWidget);
    expect(find.text('Prochains départs'), findsOneWidget);
    expect(find.text('Routes'), findsOneWidget);
  });
}
