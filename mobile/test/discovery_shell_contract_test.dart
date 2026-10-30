import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Discover root has no nested toolbar or permanent search field', () {
    final source = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final rootEnd = source.indexOf('class DiscoverySearchScreen');
    final root = source.substring(0, rootEnd);

    expect(root, isNot(contains('appBar:')));
    expect(root, isNot(contains('SearchBar(')));
    expect(
      source,
      isNot(
        contains('Le runtime Mobile ne fournit pas encore de style MapLibre'),
      ),
    );
    expect(source, isNot(contains('aucun fournisseur n’est inventé')));
  });

  test(
    'Discover map uses the configured MapLibre runtime from the same field',
    () {
      final screens = File('lib/features/discovery/discovery_screens.dart')
          .readAsStringSync();
      final presentation = File(
        'lib/features/discovery/discovery_mature_view.dart',
      ).readAsStringSync();
      final routes = File('lib/features/discovery/discovery_routes.dart')
          .readAsStringSync();

      expect(presentation, contains('ConfiguredMakoloMapView('));
      expect(presentation, contains('MakoloSpatialFrame('));
      expect(screens, contains('watchItems(_query)'));
      expect(screens, isNot(contains('watchMap(_query)')));
      expect(routes, contains('mapConfig: runtime.mapConfig'));
      expect(routes, contains("path: '/discover/map'"));
    },
  );
  test('Profile reuses guest filters without requiring location', () {
    final source = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final routes = File('lib/features/discovery/discovery_routes.dart')
        .readAsStringSync();
    final start = source.indexOf('class _DiscoverySearchScreenState');
    final end = source.indexOf('class DiscoveryMapScreen', start);
    final search = source.substring(start, end);

    expect(search, contains('ProgressiveSearchCoordinator('));
    expect(search, contains('SearchFilterBar('));
    expect(search, contains('GeoAutocompleteField('));
    expect(search, contains("Key('discover-search-nearby')"));
    expect(search, contains('clearLocation: true'));
    expect(search, contains('onChanged: _searchChanged'));
    expect(search, contains("Key('discover-search-categories')"));
    expect(search, contains("Key('discover-search-when')"));
    expect(search, contains("Key('discover-search-price')"));
    expect(search, contains('if (_query.latitude != null)'));
    expect(routes, contains('geoSearch: runtime.geoSearch'));
    expect(routes, contains('location: runtime.location'));
    expect(source, contains('class DiscoveryMapScreen'));
  });
}
