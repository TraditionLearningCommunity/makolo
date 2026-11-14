import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/features/space/space_work_g2_depth.dart';

void main() {
  testWidgets('MT4 Programme presents only real Sessions and Inscriptions', (
    tester,
  ) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => Scaffold(
            body: SingleChildScrollView(
              child: SpaceWorkG2Depth(
                slug: 'school',
                archetype: 'education',
                occurrences: const {
                  'items': [
                    {
                      'source': {'kind': 'occurrence', 'id': 'session-1'},
                      'title': 'Session du mardi',
                      'state': 'scheduled',
                      'openable': true,
                      'timing': {'start_date': '2026-11-15'},
                    },
                  ],
                  'offset': 0,
                  'limit': 12,
                  'has_more': false,
                },
                work: const {
                  'items': [
                    {
                      'source': {'kind': 'journey', 'id': 'registration-1'},
                      'title': 'Inscription',
                      'state': 'pending_approval',
                    },
                  ],
                  'offset': 0,
                  'limit': 12,
                  'has_more': false,
                },
                onOccurrencesPageChange: (_) {},
                onWorkPageChange: (_) {},
              ),
            ),
          ),
        ),
        GoRoute(
          path: '/space/:slug/retrieval/:kind/:id',
          builder: (context, state) =>
              Scaffold(body: Text(state.pathParameters['id'] ?? '')),
        ),
      ],
    );
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    expect(find.text('Sessions de ce programme'), findsOneWidget);
    expect(find.text('Inscriptions visibles'), findsOneWidget);
    expect(find.text('Session du mardi'), findsOneWidget);
    await tester.tap(find.text('Session du mardi'));
    await tester.pumpAndSettle();
    expect(find.text('session-1'), findsOneWidget);
    router.dispose();
  });

  testWidgets('MT4 service page is calm and does not invent a dossier', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SpaceWorkG2Depth(
            slug: 'services',
            archetype: 'service_provider',
            occurrences: const {
              'items': [],
              'offset': 0,
              'limit': 12,
              'has_more': false,
            },
            work: const {
              'items': [],
              'offset': 0,
              'limit': 12,
              'has_more': false,
            },
            onOccurrencesPageChange: (_) {},
            onWorkPageChange: (_) {},
          ),
        ),
      ),
    );
    expect(find.text('Réalisations liées'), findsOneWidget);
    expect(find.text('Dossiers de cette prestation'), findsOneWidget);
    expect(
      find.text('Aucun dossier visible dans votre périmètre.'),
      findsOneWidget,
    );
  });

  testWidgets('MT4 bounded pagination and elapsed realization do not lie', (
    tester,
  ) async {
    int? nextOccurrences;
    int? nextWork;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: SpaceWorkG2Depth(
              slug: 'education',
              archetype: 'education',
              occurrences: const {
                'items': [
                  {
                    'source': {'kind': 'occurrence', 'id': 'elapsed'},
                    'title': 'Session passée',
                    'state': 'scheduled',
                    'openable': false,
                  },
                ],
                'offset': 12,
                'limit': 12,
                'has_more': false,
              },
              work: const {
                'items': [],
                'offset': 12,
                'limit': 12,
                'has_more': true,
              },
              onOccurrencesPageChange: (v) => nextOccurrences = v,
              onWorkPageChange: (v) => nextWork = v,
            ),
          ),
        ),
      ),
    );
    expect(find.text('Session passée'), findsOneWidget);
    expect(find.textContaining('Date non ouvrable'), findsOneWidget);
    final prevButtons = find.text('Précédentes');
    expect(prevButtons, findsNWidgets(2));
    await tester.tap(prevButtons.first);
    expect(nextOccurrences, 0);
    await tester.tap(find.text('Voir les suivantes'));
    expect(nextWork, 24);
  });
}
