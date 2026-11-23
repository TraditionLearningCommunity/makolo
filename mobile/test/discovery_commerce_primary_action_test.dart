import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_possibility_unit.dart';

DiscoveryItemPresentation _possibility(Map<String, dynamic> engagement) {
  return DiscoveryItemPresentation(
    family: 'activity',
    id: 'test-activity',
    candidateKey: 'activity:test-activity',
    title: 'Réservation test',
    summary: 'Une possibilité à découvrir.',
    savedState: 'unknown',
    capabilities: const {'view'},
    links: const {},
    wire: {'engagement': engagement},
  );
}

Future<void> _pumpAction(
  WidgetTester tester, {
  required Map<String, dynamic> engagement,
  required void Function() onDetail,
}) async {
  final item = _possibility(engagement);
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => Scaffold(
          body: SingleChildScrollView(
            child: DiscoveryPossibilityUnit(item: item, onOpen: onDetail),
          ),
        ),
      ),
      GoRoute(
        path: '/commerce/journeys/:id/checkout',
        builder: (context, state) =>
            Scaffold(body: Text('checkout:${state.pathParameters['id']}')),
      ),
      GoRoute(
        path: '/commerce/activities/:id/checkout',
        builder: (context, state) => Scaffold(
          body: Text('activity-checkout:${state.pathParameters['id']}'),
        ),
      ),
      GoRoute(
        path: '/commerce/orders/:id',
        builder: (context, state) =>
            Scaffold(body: Text('order:${state.pathParameters['id']}')),
      ),
      GoRoute(
        path: '/journeys/:id',
        builder: (context, state) =>
            Scaffold(body: Text('journey:${state.pathParameters['id']}')),
      ),
    ],
  );
  await tester.pumpWidget(MaterialApp.router(routerConfig: router));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a verified Commerce offer continuation stays native', (
    tester,
  ) async {
    var detailCount = 0;
    await _pumpAction(
      tester,
      onDetail: () => detailCount++,
      engagement: {
        'owner': 'commerce',
        'state': 'owner_api',
        'capabilities': ['checkout'],
        'resource': {'kind': 'journey', 'id': 'journey-123'},
        'links': {'native': '/commerce/journeys/journey-123/checkout'},
        'primary_action': {
          'code': 'checkout',
          'label': 'Choisir une offre',
          'destination': {
            'kind': 'native',
            'path': '/commerce/journeys/journey-123/checkout',
          },
        },
      },
    );
    final primary = find.byKey(const Key('discover-primary-n1'));
    expect(tester.widget<IconButton>(primary).tooltip, 'Choisir une offre');
    await tester.tap(primary);
    await tester.pumpAndSettle();
    expect(find.text('checkout:journey-123'), findsOneWidget);
    expect(detailCount, 0);
  });

  testWidgets('direct Activity Commerce action opens the native offer choice', (
    tester,
  ) async {
    var details = 0;
    await _pumpAction(
      tester,
      onDetail: () => details++,
      engagement: {
        'owner': 'commerce',
        'state': 'owner_api',
        'capabilities': ['inspect_offers'],
        'resource': {'kind': 'activity', 'id': 'test-activity'},
        'links': {
          'native': '/commerce/activities/test-activity/checkout',
          'offers': '/api/v1/commerce/activities/test-activity/checkout/',
        },
        'primary_action': {
          'code': 'inspect_offers',
          'label': 'Choisir une offre',
          'destination': {
            'kind': 'native',
            'path': '/commerce/activities/test-activity/checkout',
          },
        },
      },
    );
    final primary = find.byKey(const Key('discover-primary-n1'));
    expect(tester.widget<IconButton>(primary).tooltip, 'Choisir une offre');
    await tester.tap(primary);
    await tester.pumpAndSettle();
    expect(find.text('activity-checkout:test-activity'), findsOneWidget);
    expect(details, 0);
  });

  testWidgets('an existing owner order resumes instead of recreating one', (
    tester,
  ) async {
    await _pumpAction(
      tester,
      onDetail: () {},
      engagement: {
        'owner': 'commerce',
        'state': 'owner_api',
        'capabilities': ['resume_order'],
        'resource': {'kind': 'commerce_order', 'id': 'order-123'},
        'links': {'native': '/commerce/orders/order-123'},
        'primary_action': {
          'code': 'resume_order',
          'label': 'Ma commande',
          'destination': {
            'kind': 'native',
            'path': '/commerce/orders/order-123',
          },
        },
      },
    );
    await tester.tap(find.byKey(const Key('discover-primary-n1')));
    await tester.pumpAndSettle();
    expect(find.text('order:order-123'), findsOneWidget);
  });

  testWidgets('a forged native Commerce destination opens details instead', (
    tester,
  ) async {
    var detailCount = 0;
    await _pumpAction(
      tester,
      onDetail: () => detailCount++,
      engagement: {
        'owner': 'commerce',
        'state': 'owner_api',
        'capabilities': ['checkout'],
        'resource': {'kind': 'journey', 'id': 'journey-123'},
        'links': {'native': '/commerce/journeys/journey-123/checkout'},
        'primary_action': {
          'code': 'checkout',
          'label': 'Payer',
          'destination': {
            'kind': 'native',
            'path': '/payments/obligations/unknown',
          },
        },
      },
    );
    final primary = find.byKey(const Key('discover-primary-n1'));
    expect(tester.widget<IconButton>(primary).tooltip, 'Détails');
    await tester.tap(primary);
    await tester.pumpAndSettle();
    expect(detailCount, 1);
  });
}
