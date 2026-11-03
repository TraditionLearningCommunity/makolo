import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway.dart';
import 'package:makolo_mobile/presentation/fields/discovery_filter_fields.dart';
import 'package:makolo_mobile/presentation/fields/search_filter_bar.dart';

class _Suggestions implements GeoSearchGateway {
  @override
  Future<List<GeoSuggestion>> suggest(
    String query, {
    String language = 'fr',
    int limit = 5,
    GeoSearchCancellation? cancelToken,
  }) async {
    return const [
      GeoSuggestion(
        id: 'provider-kinshasa',
        label: 'Kinshasa, République démocratique du Congo',
        longitude: 15.31,
        latitude: -4.32,
        source: 'test-provider',
      ),
    ];
  }
}

void main() {
  testWidgets(
    'keyboard-sized Discovery filters scroll and reveal geo matches',
    (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final place = TextEditingController();
      addTearDown(place.dispose);
      GeoSuggestion? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(360, 640),
              viewInsets: EdgeInsets.only(bottom: 260),
            ),
            child: Scaffold(
              body: Column(
                children: [
                  Flexible(
                    fit: FlexFit.loose,
                    child: SingleChildScrollView(
                      child: Column(
                        children: [
                          SearchFilterBar(
                            filterButtonKey: const Key('keyboard-toggle'),
                            filterPanelKey: const Key('keyboard-filters'),
                            searchField: const TextField(),
                            filters: DiscoveryFilterFields(
                              keyPrefix: 'keyboard',
                              placeController: place,
                              geoSearch: _Suggestions(),
                              when: '',
                              date: '',
                              price: '',
                              onPlaceSelected: (value) => selected = value,
                              onPlaceEdited: () {},
                              onPlaceSubmitted: () {},
                              onWhenChanged: (_) {},
                              onChooseDate: () {},
                              onPriceChanged: (_) {},
                            ),
                            showResultsAction: true,
                            onClearFilters: () {},
                          ),
                          DiscoveryCategoryChips(
                            selected: '',
                            onSelected: (_) {},
                            listKey: const Key('keyboard-categories'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const Expanded(child: Center(child: Text('Résultats'))),
                ],
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.byKey(const Key('keyboard-toggle')));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);

      await tester.ensureVisible(find.byKey(const Key('keyboard-place')));
      await tester.enterText(
        find.byKey(const Key('keyboard-place')),
        'kinchassa',
      );
      await tester.pump(const Duration(milliseconds: 360));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('geo-suggestions')), findsOneWidget);
      await tester.ensureVisible(
        find.text('Kinshasa, République démocratique du Congo'),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Kinshasa, République démocratique du Congo'));
      await tester.pumpAndSettle();
      expect(selected?.id, 'provider-kinshasa');
      expect(place.text, 'Kinshasa, République démocratique du Congo');
      expect(tester.takeException(), isNull);

      await tester.ensureVisible(
        find.byKey(const Key('discovery-show-results')),
      );
      await tester.tap(find.byKey(const Key('discovery-show-results')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('keyboard-filters')), findsNothing);
      expect(find.text('Résultats'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
