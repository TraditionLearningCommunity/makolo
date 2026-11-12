import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/occurrence/occurrence_experience_content.dart';

void main() {
  testWidgets('Jour J can open owner-protected QR depth offline', (
    tester,
  ) async {
    String? openedAccess;
    String? openedPath;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OccurrenceExperienceContent(
            payload: const {
              'surface': 'day_of',
              'phase': 'arrival',
              'context': {
                'activity': {'title': 'Formation'},
                'occurrence': {'label': 'Session'},
              },
              'live': {'available': false},
              'sections': {
                'participant': {
                  'access': [
                    {
                      'identity': {'id': 'access-1'},
                      'state': 'valid',
                      'usable': true,
                      'credential': {'presentable': true},
                      'links': {
                        'credential': '/api/v1/me/accesses/access-1/credential/',
                      },
                    },
                  ],
                  'queue': [],
                  'placement': [],
                },
              },
              'actions': [],
              'capabilities': {},
            },
            live: false,
            remoteActionsAvailable: false,
            readOnlyReason: 'Dernière information connue.',
            onPresentCredential: (accessId, credentialPath) {
              openedAccess = accessId;
              openedPath = credentialPath;
            },
          ),
        ),
      ),
    );
    final button = find.widgetWithText(FilledButton, 'Présenter mon accès');
    await tester.ensureVisible(button);
    expect(tester.widget<FilledButton>(button).onPressed, isNotNull);
    await tester.tap(button);
    expect(openedAccess, 'access-1');
    expect(openedPath, '/api/v1/me/accesses/access-1/credential/');
  });

  testWidgets('Jour J can show participant and organizer moves together', (
    tester,
  ) async {
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

  testWidgets(
    'Makolo Live shows coverage and owner facts without fake streaming',
    (tester) async {
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
    },
  );
  testWidgets('L5 independent owner depths keep direct actions visible', (
    tester,
  ) async {
    String? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OccurrenceExperienceContent(
            payload: const {
              'surface': 'day_of',
              'phase': 'arrival',
              'context': {
                'activity': {'title': 'Départ'},
                'occurrence': {'label': 'Départ du jour'},
              },
              'live': {'available': false},
              'sections': {
                'organizer': {
                  'operational_readiness': {'state': 'ready'},
                  'queue': [],
                  'capacity': [],
                  'checkpoints': [],
                },
              },
              'actions': [],
              'capabilities': {'finance_view': {}, 'operations_manage': {}},
              'depths': [
                {'kind': 'finance', 'label': 'Finances'},
                {'kind': 'operator_queue', 'label': 'Gérer les files'},
              ],
            },
            live: false,
            onOpenDepth: (kind) => selected = kind,
          ),
        ),
      ),
    );
    await tester.scrollUntilVisible(find.text('Finances'), 170);
    await tester.tap(find.text('Finances'));
    expect(selected, 'finance');
    await tester.scrollUntilVisible(find.text('Gérer les files'), 170);
    await tester.tap(find.text('Gérer les files'));
    expect(selected, 'operator_queue');
    expect(find.byType(DropdownButton<String>), findsNothing);
  });
}
