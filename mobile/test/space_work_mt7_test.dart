import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/features/space/space_work_owner_actions.dart';
import 'package:makolo_mobile/features/space/space_work_surface.dart';
import 'package:makolo_mobile/presentation/contracts/space_presentation.dart';

void main() {
  test(
    'MT7 Work origin carries only bounded section and collection context',
    () {
      final route = spaceWorkOwnerRoute(
        slug: 'atelier',
        kind: 'activity',
        id: 'work-1',
        section: 'activities',
        fromCollection: true,
      );
      expect(route, contains('work_section=activities'));
      expect(route, contains('work_collection=1'));
      expect(
        spaceWorkOwnerRoute(
          slug: 'atelier',
          kind: 'activity',
          id: 'work-1',
          section: 'foreign',
        ),
        '/space/atelier/retrieval/activity/work-1',
      );
      expect(
        spaceWorkReturnRoute(
          slug: 'atelier',
          section: 'activities',
          fromCollection: true,
        ),
        '/space/atelier/work/activities',
      );
      expect(
        spaceWorkReturnRoute(
          slug: 'atelier',
          section: 'foreign',
          fromCollection: true,
        ),
        '/space/work',
      );
    },
  );

  testWidgets('MT7 respects server chapter and section order', (tester) async {
    tester.view.physicalSize = const Size(1200, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SpaceWorkSurface(
            payload: {
              'space': {'slug': 'atelier'},
              'archetype': 'education',
              'responsibility': 'all',
              'primary_business_label': 'Programmes',
              'coverage_state': 'established',
              'capabilities': {},
              'presentation': {
                'question': 'Quels programmes faisons-nous vivre ?',
                'section_order': ['activities', 'upcoming'],
                'reading_groups': [
                  {
                    'representation': 'Nos programmes',
                    'section_keys': ['activities'],
                  },
                  {
                    'representation': 'Sessions et préparation',
                    'section_keys': ['upcoming'],
                  },
                ],
              },
              'sections': {
                'upcoming': {
                  'representation': 'Prochaines sessions',
                  'items': [
                    {
                      'title': 'Séance lundi',
                      'source': {'kind': 'occurrence', 'id': 'occ-1'},
                      'context': {},
                      'capabilities': [],
                    },
                  ],
                },
                'activities': {
                  'representation': 'Programmes',
                  'items': [
                    {
                      'title': 'Programme Comptabilité',
                      'source': {'kind': 'activity', 'id': 'act-1'},
                      'context': {},
                      'capabilities': [],
                    },
                  ],
                },
              },
            },
          ),
        ),
      ),
    );
    expect(find.text('Nos programmes'), findsOneWidget);
    expect(find.text('Sessions et préparation'), findsOneWidget);
    expect(find.text('Quels programmes faisons-nous vivre ?'), findsOneWidget);
    final work = tester.getTopLeft(find.text('Programme Comptabilité'));
    final session = tester.getTopLeft(find.text('Séance lundi'));
    expect(work.dy, lessThan(session.dy));
  });

  testWidgets('MT7 partial empty never pretends whole Space has no work', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SpaceWorkSurface(
            payload: {
              'space': {'slug': 'atelier'},
              'primary_business_label': 'Métier',
              'composition_state': 'partial',
              'coverage_state': 'partial',
              'presentation': {'empty_message': 'Aucune activité globale.'},
              'sections': {},
            },
          ),
        ),
      ),
    );
    expect(find.textContaining('Cette vue est partielle'), findsOneWidget);
    expect(find.text('Aucune activité globale.'), findsNothing);
  });

  testWidgets('MT7 Work N1 opens owner with chapter return context', (
    tester,
  ) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const Scaffold(
            body: SpaceWorkSurface(
              payload: {
                'space': {'slug': 'atelier'},
                'archetype': 'creative',
                'responsibility': 'all',
                'primary_business_label': 'Créations',
                'capabilities': {},
                'presentation': {
                  'section_order': ['activities'],
                },
                'sections': {
                  'activities': {
                    'representation': 'Créations',
                    'items': [
                      {
                        'title': 'Œuvre durable',
                        'source': {'kind': 'activity', 'id': 'work-1'},
                        'context': {},
                        'capabilities': ['view'],
                      },
                    ],
                  },
                },
              },
            ),
          ),
        ),
        GoRoute(
          path: '/space/:slug/retrieval/:kind/:id',
          builder: (context, state) => Scaffold(
            body: Text(
              state.uri.queryParameters['work_section'] ?? 'No work origin',
            ),
          ),
        ),
      ],
    );
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.tap(find.text('Œuvre durable'));
    await tester.pumpAndSettle();
    expect(find.text('activities'), findsOneWidget);
    router.dispose();
  });

  testWidgets('MT7 owner actions reject Web, foreign owners and fake links', (
    tester,
  ) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const Scaffold(
            body: SpaceWorkOwnerActions(
              slug: 'atelier',
              sourceKind: 'journey',
              sourceId: 'journey-1',
              archetype: 'education',
              handoffs: [
                {
                  'intent': 'open_request',
                  'channel': 'web',
                  'owner': {'kind': 'journey_request', 'id': 'web-1'},
                  'url': '/api/v1/requests/web-1/',
                },
                {
                  'intent': 'open_request',
                  'channel': 'api',
                  'owner': {'kind': 'journey_request', 'id': 'foreign'},
                  'url': 'https://foreign.test/api/v1/requests/foreign/',
                },
                {
                  // Same owner id as a substring, wrong canonical path.
                  'intent': 'open_request',
                  'channel': 'api',
                  'owner': {'kind': 'journey_request', 'id': 'request-1'},
                  'url': '/api/v1/organizations/workspaces/atelier/requests/request-1-forged/',
                },
                {
                  'intent': 'open_day_of',
                  'channel': 'api',
                  'owner': {'kind': 'occurrence', 'id': 'wrong'},
                  'url': '/api/v1/occurrences/wrong/day-of/',
                },
                {
                  'intent': 'open_request',
                  'channel': 'api',
                  'owner': {'kind': 'journey_request', 'id': 'request-1'},
                  'url': '/api/v1/organizations/workspaces/atelier/requests/request-1/',
                },
              ],
            ),
          ),
        ),
        GoRoute(
          path: '/space/requests/:id',
          builder: (context, state) =>
              Scaffold(body: Text(state.pathParameters['id'] ?? '')),
        ),
      ],
    );
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    expect(find.text('Examiner la demande'), findsOneWidget);
    expect(find.text('Jour J'), findsNothing);
    expect(find.text('Suivre le dossier de prestation'), findsNothing);
    await tester.tap(find.text('Examiner la demande'));
    await tester.pumpAndSettle();
    expect(find.text('request-1'), findsOneWidget);
    router.dispose();
  });
}
