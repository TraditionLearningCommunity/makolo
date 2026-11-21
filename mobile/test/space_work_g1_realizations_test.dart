import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/features/space/space_work_g1_realizations.dart';

void main() {
  testWidgets('empty G1 Activity remains valid without an Occurrence', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SpaceWorkG1Realizations(
            payload: const {
              'items': [],
              'has_more': false,
              'offset': 0,
              'limit': 12,
            },
            slug: 'community-space',
            onPageChange: (_) {},
          ),
        ),
      ),
    );
    expect(find.text('Dates et réalisations'), findsOneWidget);
    expect(find.textContaining('Aucune réalisation datée'), findsOneWidget);
    expect(find.text('Voir les suivantes'), findsNothing);
  });

  testWidgets('paginates real owner rows without inventing a Live action', (
    tester,
  ) async {
    int? requested;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SpaceWorkG1Realizations(
            payload: const {
              'items': [
                {
                  'source': {'kind': 'occurrence', 'id': 'old-1'},
                  'title': 'Action passée sans état terminal',
                  'state': 'scheduled',
                  'timing': {'start_date': '2026-01-12'},
                  'openable': false,
                },
              ],
              'has_more': true,
              'offset': 12,
              'limit': 12,
            },
            slug: 'community-space',
            onPageChange: (offset) => requested = offset,
          ),
        ),
      ),
    );
    expect(find.text('Action passée sans état terminal'), findsOneWidget);
    expect(find.textContaining('Date non ouvrable ici'), findsOneWidget);
    expect(find.byIcon(Icons.chevron_right), findsNothing);
    await tester.tap(find.text('Précédentes'));
    expect(requested, 0);
    await tester.tap(find.text('Voir les suivantes'));
    expect(requested, 24);
  });

  testWidgets('opens only a verified selectable Occurrence', (tester) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => Scaffold(
            body: SpaceWorkG1Realizations(
              payload: const {
                'items': [
                  {
                    'source': {'kind': 'occurrence', 'id': 'occ-verified'},
                    'title': 'Action terrain',
                    'state': 'scheduled',
                    'timing': {'start_date': '2026-11-12'},
                    'openable': true,
                  },
                ],
                'has_more': false,
                'offset': 0,
                'limit': 12,
              },
              slug: 'community-space',
              onPageChange: (_) {},
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
    await tester.tap(find.text('Action terrain'));
    await tester.pumpAndSettle();
    expect(find.text('occ-verified'), findsOneWidget);
    router.dispose();
  });
}
