import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_directions_sheet.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';

DiscoveryItemPresentation _item(List<Map<String, dynamic>> facts) =>
    DiscoveryItemPresentation(
      family: 'activity',
      id: 'journey',
      candidateKey: 'activity:journey',
      title: 'Trajet de démonstration',
      summary: '',
      capabilities: const {'view'},
      links: const {},
      savedState: 'not_saved',
      wire: {'spatial_facts': facts},
    );

void main() {
  test('Journey directions preserve published departure and arrival roles', () {
    final item = _item([
      {
        'role': 'departure',
        'place': {
          'name': 'Lubumbashi',
          'latitude': -11.66,
          'longitude': 27.48,
        },
      },
      {
        'role': 'arrival',
        'place': {
          'name': 'Montréal',
          'latitude': 45.5,
          'longitude': -73.56,
        },
      },
      {
        'role': 'stopover',
        'place': {
          'name': 'Doublon Montréal',
          'latitude': 45.5,
          'longitude': -73.56,
        },
      },
    ]);
    final places = discoveryDirectionsDestinations(item);
    expect(places, hasLength(2));
    expect(places.first.label, 'Départ · Lubumbashi');
    expect(places.last.label, 'Arrivée · Montréal');
    expect(places.last.latitude, 45.5);
  });

  test('private/malformed or missing coordinates never fabricate a route', () {
    final item = _item([
      {'role': 'primary', 'place': {'name': 'Sans coordonnées'}},
      {'role': 'arrival', 'place': {
        'latitude': 95,
        'longitude': 27,
      }},
    ]);
    expect(discoveryDirectionsDestinations(item), isEmpty);
  });

  testWidgets('Itinerary offers Google Maps and Waze without an internal router',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: Builder(
        builder: (context) => TextButton(
          onPressed: () => unawaited(
            showDiscoveryDirections(
              context, latitude: -29.315, longitude: 27.483,
            ),
          ),
          child: const Text('Itinéraire'),
        ),
      )),
    ));
    await tester.tap(find.text('Itinéraire'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('discover-directions-google')), findsOneWidget);
    expect(find.byKey(const Key('discover-directions-waze')), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
