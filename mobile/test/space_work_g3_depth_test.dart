import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/features/space/space_work_g3_depth.dart';

void main() {
  testWidgets(
    'MT5 Commerce order shows historical lines, not payment success',
    (tester) async {
      int? offset;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                SpaceWorkG3Depth(
                  slug: 'boutique',
                  ownerId: 'order-1',
                  payload: const {
                    'kind': 'commerce_order',
                    'facts': {
                      'reference': 'CMD-123',
                      'currency': 'USD',
                      'subtotal': '18.00',
                      'discount_total': '0.00',
                      'total': '18.00',
                      'payment_mode': 'upfront',
                      'payment_state': 'not_projected',
                      'delivery_state': 'not_projected',
                    },
                    'lines': {
                      'offset': 0,
                      'limit': 12,
                      'has_more': true,
                      'items': [
                        {
                          'label': 'Ancien kit acheté',
                          'quantity': 2,
                          'unit_price': '9.00',
                          'line_total': '18.00',
                          'currency': 'USD',
                        },
                      ],
                    },
                  },
                  onPageChange: (next) => offset = next,
                  onSecondaryPageChange: (_) {},
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Commande CMD-123'), findsOneWidget);
      expect(find.textContaining('Total commandé'), findsOneWidget);
      expect(find.text('Ancien kit acheté'), findsOneWidget);
      expect(
        find.textContaining('Commande confirmée ne signifie'),
        findsOneWidget,
      );
      expect(find.textContaining('Payé'), findsNothing);
      await tester.ensureVisible(find.text('Voir les suivants'));
      await tester.tap(find.text('Voir les suivants'));
      expect(offset, 12);
    },
  );

  testWidgets(
    'MT5 Offer never enables editing without Commerce owner permission',
    (tester) async {
      Future<void> render(bool allowed) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpaceWorkG3Depth(
              slug: 'boutique',
              ownerId: 'offer-1',
              payload: {
                'kind': 'offer',
                'facts': {
                  'unit_price': '25.00',
                  'currency': 'USD',
                  'currently_available': false,
                  'can_manage_offer': allowed,
                  'min_quantity': 1,
                  'max_quantity': 2,
                  'payment_mode': 'upfront',
                },
              },
              onPageChange: (_) {},
              onSecondaryPageChange: (_) {},
            ),
          ),
        ),
      );
      await render(false);
      expect(find.text('Modifier l’offre'), findsNothing);
      expect(
        find.textContaining('Non disponible selon le propriétaire'),
        findsOneWidget,
      );
      await render(true);
      expect(find.text('Modifier l’offre'), findsOneWidget);
    },
  );

  testWidgets(
    'MT5 Transport route opens a real departure but not an elapsed one',
    (tester) async {
      int? next;
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => Scaffold(
              body: ListView(
                children: [
                  SpaceWorkG3Depth(
                    slug: 'transport',
                    ownerId: 'route-1',
                    payload: const {
                      'kind': 'transport_route',
                      'facts': {'active': true},
                      'departures': {
                        'offset': 12,
                        'limit': 12,
                        'has_more': true,
                        'items': [
                          {
                            'source': {'kind': 'occurrence', 'id': 'old'},
                            'title': 'Départ passé',
                            'state': 'scheduled',
                            'openable': false,
                          },
                          {
                            'source': {'kind': 'occurrence', 'id': 'future'},
                            'title': 'Départ futur',
                            'state': 'scheduled',
                            'openable': true,
                          },
                        ],
                      },
                    },
                    onPageChange: (_) {},
                    onSecondaryPageChange: (v) => next = v,
                  ),
                ],
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
      expect(find.text('Départ passé'), findsOneWidget);
      expect(find.text('Départ futur'), findsOneWidget);
      expect(find.textContaining('carte n’est affichée'), findsOneWidget);
      expect(find.text('Précédents'), findsOneWidget);
      await tester.ensureVisible(find.text('Voir les suivants'));
      await tester.tap(find.text('Voir les suivants'));
      expect(next, 24);
      await tester.ensureVisible(find.text('Départ futur'));
      await tester.tap(find.text('Départ futur'));
      await tester.pumpAndSettle();
      expect(find.text('future'), findsOneWidget);
      router.dispose();
    },
  );

  testWidgets(
    'MT5 departure N3 action is available only with manage authority',
    (tester) async {
      Future<void> render(bool manage) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpaceWorkG3Depth(
              slug: 'transport',
              ownerId: 'occurrence-1',
              payload: {
                'kind': 'transport_departure',
                'facts': {
                  'departure_id': 'departure-1',
                  'route': {'name': 'Lubumbashi → Kolwezi'},
                  'operations_visible': true,
                  'can_manage_operations': manage,
                  'vehicle_assignment_known': true,
                  'vehicle': null,
                },
              },
              onPageChange: _ignore,
              onSecondaryPageChange: _ignore,
            ),
          ),
        ),
      );
      await render(false);
      expect(find.text('Exploiter ce départ'), findsNothing);
      expect(find.textContaining('Véhicule : Non affecté'), findsOneWidget);
      await render(true);
      expect(find.text('Exploiter ce départ'), findsOneWidget);
    },
  );

  testWidgets('MT5 Transport physical capacity never implies available seats', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SpaceWorkG3Depth(
            slug: 'transport',
            payload: {
              'kind': 'vehicle',
              'facts': {
                'vehicle_type': 'bus',
                'passenger_capacity': 40,
                'active': true,
              },
            },
            onPageChange: _ignore,
            onSecondaryPageChange: _ignore,
          ),
        ),
      ),
    );
    expect(find.textContaining('Places physiques : 40'), findsOneWidget);
    expect(find.textContaining('ne sont ni une réservation'), findsOneWidget);
    expect(find.textContaining('Places vendables : 40'), findsNothing);
  });
}

void _ignore(int _) {}
