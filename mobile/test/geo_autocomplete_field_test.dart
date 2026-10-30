import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway.dart';
import 'package:makolo_mobile/presentation/fields/geo_autocomplete_field.dart';

class _FakeGeoSearch implements GeoSearchGateway {
  final calls = <String>[];
  final requests = <Completer<List<GeoSuggestion>>>[];

  @override
  Future<List<GeoSuggestion>> suggest(
    String query, {
    String language = 'fr',
    int limit = 5,
    GeoSearchCancellation? cancelToken,
  }) {
    calls.add(query);
    final request = Completer<List<GeoSuggestion>>();
    requests.add(request);
    return request.future;
  }
}

void main() {
  testWidgets('without provider keeps free text search usable', (tester) async {
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    var submitted = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GeoAutocompleteField(
            controller: controller,
            fieldKey: const Key('place'),
            onSubmitted: () => submitted++,
          ),
        ),
      ),
    );

    await tester.enterText(find.byKey(const Key('place')), 'Kolwezi');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();
    expect(controller.text, 'Kolwezi');
    expect(submitted, 1);
    expect(find.byKey(const Key('geo-suggestions')), findsNothing);
    expect(
      find.byKey(const Key('geo-suggestions-unconfigured')),
      findsOneWidget,
    );
  });

  testWidgets('debounces requests, selects a structured place', (tester) async {
    final gateway = _FakeGeoSearch();
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    GeoSuggestion? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GeoAutocompleteField(
            controller: controller,
            gateway: gateway,
            fieldKey: const Key('place'),
            onSelected: (value) => selected = value,
          ),
        ),
      ),
    );
    await tester.enterText(find.byKey(const Key('place')), 'K');
    await tester.pump(const Duration(milliseconds: 150));
    await tester.enterText(find.byKey(const Key('place')), 'Ko');
    await tester.pump(const Duration(milliseconds: 349));
    expect(gateway.calls, isEmpty);
    await tester.pump(const Duration(milliseconds: 2));
    expect(gateway.calls, ['Ko']);
    gateway.requests.single.complete(const [
      GeoSuggestion(
        id: 'place.1',
        label: 'Kolwezi, Lualaba, RD Congo',
        latitude: -10.72,
        longitude: 25.47,
        source: 'maptiler',
        kind: 'place',
      ),
    ]);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Kolwezi, Lualaba, RD Congo'));
    await tester.pumpAndSettle();
    expect(selected?.id, 'place.1');
    expect(selected?.latitude, -10.72);
    expect(controller.text, 'Kolwezi, Lualaba, RD Congo');
    expect(find.byKey(const Key('geo-suggestions')), findsNothing);
  });

  testWidgets('late results never replace more recent typing', (tester) async {
    final gateway = _FakeGeoSearch();
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GeoAutocompleteField(
            controller: controller,
            gateway: gateway,
            fieldKey: const Key('place'),
          ),
        ),
      ),
    );
    await tester.enterText(find.byKey(const Key('place')), 'Kin');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.enterText(find.byKey(const Key('place')), 'Kol');
    await tester.pump(const Duration(milliseconds: 360));
    gateway.requests.last.complete(const [
      GeoSuggestion(
        id: 'place.2',
        label: 'Kolwezi, RD Congo',
        latitude: -10.72,
        longitude: 25.47,
        source: 'maptiler',
      ),
    ]);
    await tester.pump();
    gateway.requests.first.complete(const [
      GeoSuggestion(
        id: 'place.old',
        label: 'Kinshasa, RD Congo',
        latitude: -4.32,
        longitude: 15.31,
        source: 'maptiler',
      ),
    ]);
    await tester.pumpAndSettle();
    expect(find.text('Kolwezi, RD Congo'), findsOneWidget);
    expect(find.text('Kinshasa, RD Congo'), findsNothing);
  });

  testWidgets('provider error leaves entry editable with honest fallback', (
    tester,
  ) async {
    final gateway = _FakeGeoSearch();
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GeoAutocompleteField(
            controller: controller,
            gateway: gateway,
            fieldKey: const Key('place'),
          ),
        ),
      ),
    );
    await tester.enterText(find.byKey(const Key('place')), 'K');
    await tester.pump(const Duration(milliseconds: 360));
    gateway.requests.single.completeError(
      const GeoSearchException('unavailable'),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('geo-suggestions-error')), findsOneWidget);
    expect(controller.text, 'K');
  });


  testWidgets('owner clear removes visible provider suggestions', (tester) async {
    final gateway = _FakeGeoSearch();
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GeoAutocompleteField(
            controller: controller,
            gateway: gateway,
            fieldKey: const Key('place'),
          ),
        ),
      ),
    );
    await tester.enterText(find.byKey(const Key('place')), 'kinchassa');
    await tester.pump(const Duration(milliseconds: 360));
    gateway.requests.single.complete(const [
      GeoSuggestion(
        id: 'kinshasa',
        label: 'Kinshasa, RD Congo',
        latitude: -4.32,
        longitude: 15.31,
        source: 'maptiler',
      ),
    ]);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('geo-suggestions')), findsOneWidget);
    controller.clear();
    await tester.pump();
    expect(find.byKey(const Key('geo-suggestions')), findsNothing);
    expect(find.text('Kinshasa, RD Congo'), findsNothing);
  });

  testWidgets('clear control resets manual place and notifies owner', (
    tester,
  ) async {
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    var edits = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GeoAutocompleteField(
            controller: controller,
            fieldKey: const Key('place'),
            onEdited: () => edits++,
          ),
        ),
      ),
    );

    await tester.enterText(find.byKey(const Key('place')), 'Lagos');
    await tester.pump();
    expect(find.byKey(const Key('geo-search-clear')), findsOneWidget);
    await tester.tap(find.byKey(const Key('geo-search-clear')));
    await tester.pump();
    expect(controller.text, isEmpty);
    expect(edits, 2);
    expect(find.byKey(const Key('geo-suggestions')), findsNothing);
  });
}
