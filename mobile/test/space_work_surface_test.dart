import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/space/space_work_surface.dart';

void main() {
  testWidgets(
    'MT5 Transport creator requires direct owner capability and all lens',
    (tester) async {
      Future<void> render({
        required String archetype,
        required bool allowed,
        String responsibility = 'all',
      }) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpaceWorkSurface(
              payload: {
                'primary_business_label': 'Métier',
                'archetype': archetype,
                'responsibility': responsibility,
                'space': {'slug': 'mt5-space'},
                'capabilities': {'create_transport': allowed},
                'presentation': {'empty_message': 'Aucun départ.'},
                'sections': <String, dynamic>{},
              },
            ),
          ),
        ),
      );
      await render(archetype: 'transport_operator', allowed: true);
      expect(find.text('Planifier dans Transport'), findsOneWidget);
      await render(archetype: 'transport_operator', allowed: false);
      expect(find.text('Planifier dans Transport'), findsNothing);
      await render(
        archetype: 'transport_operator',
        allowed: true,
        responsibility: 'mandate:scoped',
      );
      expect(find.text('Planifier dans Transport'), findsNothing);
      await render(archetype: 'commerce', allowed: true);
      expect(find.text('Planifier dans Transport'), findsNothing);
    },
  );

  testWidgets(
    'MT4 Programmes and Prestations create only with Space owner capability',
    (tester) async {
      Future<void> show({
        required String archetype,
        required bool permitted,
        String responsibility = 'all',
      }) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpaceWorkSurface(
              payload: {
                'primary_business_label': 'Métier',
                'archetype': archetype,
                'responsibility': responsibility,
                'space': {'slug': 'mt4-space'},
                'capabilities': {'create_g2': permitted},
                'presentation': {'empty_message': 'Rien pour le moment.'},
                'sections': <String, dynamic>{},
              },
            ),
          ),
        ),
      );
      await show(archetype: 'education', permitted: true);
      expect(find.text('Nouveau programme'), findsOneWidget);
      await show(archetype: 'service_provider', permitted: true);
      expect(find.text('Nouvelle prestation'), findsOneWidget);
      await show(archetype: 'service_provider', permitted: false);
      expect(find.text('Nouvelle prestation'), findsNothing);
      await show(
        archetype: 'education',
        permitted: true,
        responsibility: 'mandate:restricted',
      );
      expect(find.text('Nouveau programme'), findsNothing);
      await show(archetype: 'commerce', permitted: true);
      expect(find.text('Nouvelle prestation'), findsNothing);
    },
  );

  testWidgets(
    'MT3 G1 native creation follows owner capability and perspective',
    (tester) async {
      Future<void> render({
        required String archetype,
        required bool allowed,
        String responsibility = 'all',
      }) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpaceWorkSurface(
              payload: {
                'primary_business_label': 'Métier',
                'archetype': archetype,
                'responsibility': responsibility,
                'space': {'slug': 'mt3-space'},
                'capabilities': {'create_activity': allowed},
                'presentation': {'empty_message': 'Aucun élément.'},
                'sections': <String, dynamic>{},
              },
            ),
          ),
        ),
      );

      await render(archetype: 'community', allowed: true);
      expect(find.text('Nouvelle initiative'), findsOneWidget);
      await render(archetype: 'generic', allowed: true);
      expect(find.text('Nouvelle activité'), findsOneWidget);
      await render(archetype: 'generic', allowed: false);
      expect(find.text('Nouvelle activité'), findsNothing);
      await render(
        archetype: 'community',
        allowed: true,
        responsibility: 'mandate:limited',
      );
      expect(find.text('Nouvelle initiative'), findsNothing);
      await render(archetype: 'education', allowed: true);
      expect(find.text('Nouvelle activité'), findsNothing);
    },
  );

  testWidgets('generic work empty state stays honest and calm', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SpaceWorkSurface(
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
        home: Scaffold(
          body: SpaceWorkSurface(
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
        home: Scaffold(
          body: SpaceWorkSurface(
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
      ),
    );
    expect(find.text('Transport'), findsOneWidget);
    expect(find.text('Prochains départs'), findsOneWidget);
    expect(find.text('Routes'), findsOneWidget);
  });
}
