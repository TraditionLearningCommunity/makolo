import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_map_place_search.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway.dart';

class _MapPlacesStub implements GeoSearchGateway {
  final requests = <String>[];

  @override
  Future<List<GeoSuggestion>> suggest(
    String query, {
    String language = 'fr',
    int limit = 5,
    GeoSearchCancellation? cancelToken,
  }) async {
    requests.add(query);
    return [
      const GeoSuggestion(
        id: 'maseru',
        label: 'Maseru, Lesotho',
        longitude: 27.483,
        latitude: -29.315,
        source: 'maptiler',
      ),
    ];
  }
}

void main() {
  testWidgets(
    'Carte reuses geographic autocomplete and returns real coordinates',
    (tester) async {
      final gateway = _MapPlacesStub();
      GeoSuggestion? chosen;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => unawaited(
                  chooseDiscoveryMapPlace(
                    context,
                    gateway: gateway,
                  ).then((value) => chosen = value),
                ),
                child: const Text('Lieux'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Lieux'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('discover-map-place-field')), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('discover-map-place-field')),
        'Maseru',
      );
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(gateway.requests, ['Maseru']);
      await tester.tap(find.text('Maseru, Lesotho'));
      await tester.pumpAndSettle();
      expect(chosen?.latitude, -29.315);
      expect(chosen?.longitude, 27.483);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Carte search closes without changing Discovery if cancelled', (
    tester,
  ) async {
    final gateway = _MapPlacesStub();
    GeoSuggestion? chosen;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => unawaited(
                chooseDiscoveryMapPlace(
                  context,
                  gateway: gateway,
                ).then((value) => chosen = value),
              ),
              child: const Text('Lieux'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Lieux'));
    await tester.pumpAndSettle();
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(chosen, isNull);
    expect(gateway.requests, isEmpty);
  });
}
