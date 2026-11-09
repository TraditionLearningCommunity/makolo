import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/occurrence/occurrence_experience_content.dart';

void main() {
  testWidgets('Jour J can show participant and organizer moves together', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OccurrenceExperienceContent(
            payload: const {
              'surface': 'day_of',
              'phase': 'arrival',
              'context': {
                'activity': {'title': 'Formation'},
                'occurrence': {'label': 'Session 1'},
              },
              'live': {'available': false},
              'links': {'day_of': '/occurrences/1/day-of'},
              'sections': {
                'participant': {'access': [], 'queue': [], 'placement': []},
                'organizer': {
                  'operational_readiness': {'state': 'ready'},
                  'queue': [],
                  'capacity': [],
                  'checkpoints': [],
                },
              },
              'actions': [
                {
                  'territory': 'participant',
                  'kind': 'instruction',
                  'label': 'Présenter mon accès',
                },
                {
                  'territory': 'organizer',
                  'kind': 'instruction',
                  'label': 'Préparer les entrées',
                },
              ],
              'capabilities': {},
            },
            live: false,
            onOpenLive: (_) {},
          ),
        ),
      ),
    );
    expect(find.text('Présenter mon accès'), findsOneWidget);
    expect(find.text('Préparer les entrées'), findsOneWidget);
    expect(find.text('Consulter Makolo Live'), findsNothing);
    expect(find.byType(DropdownButton<String>), findsNothing);
  });

  testWidgets('Makolo Live shows coverage and owner facts without fake streaming', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OccurrenceExperienceContent(
            payload: const {
              'surface': 'live',
              'phase': 'live',
              'context': {
                'activity': {'title': 'Voyage'},
                'occurrence': {'label': 'Départ'},
              },
              'knowledge': {
                'coverage': {'state': 'PARTIAL'},
                'planned_timing': {
                  'truth': 'planned',
                  'start_at': '2026-11-09T10:00:00+01:00',
                },
                'temporal_observation': {'truth': 'unknown'},
                'spatial': {},
                'facts': [
                  {
                    'domain': 'participant',
                    'label': 'Mon appel',
                    'truth': 'observed',
                    'source': 'operations.queue',
                    'value': 'called',
                    'occurred_at': null,
                  },
                ],
                'transitions': {'state': 'unavailable'},
              },
            },
            live: true,
          ),
        ),
      ),
    );
    expect(find.text('Couverture partielle'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Mon appel'), 160);
    expect(find.text('Mon appel'), findsOneWidget);
    expect(find.textContaining('Source : operations.queue'), findsOneWidget);
  });
}
