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
  test('guest and Profile compose the same Discovery filter controls', () {
    final personal = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final guest = File('lib/features/guest/guest_screen.dart')
        .readAsStringSync();
    final shared = File('lib/presentation/fields/discovery_filter_fields.dart')
        .readAsStringSync();
    final routes = File('lib/features/discovery/discovery_routes.dart')
        .readAsStringSync();

    expect(personal, contains('DiscoveryFilterFields('));
    expect(guest, contains('DiscoveryFilterFields('));
    expect(personal, contains('DiscoveryCategoryChips('));
    expect(guest, contains('DiscoveryCategoryChips('));
    expect(personal, isNot(contains('GeoAutocompleteField(')));
    expect(guest, isNot(contains('GeoAutocompleteField(')));
    expect(shared, contains('GeoAutocompleteField('));
    expect(shared, contains('DropdownButtonFormField<String>('));
    expect(shared, contains('onWhenChanged'));
    expect(shared, contains('onPriceChanged'));
    expect(shared, contains('onChooseDate'));
    expect(shared, contains('onPlaceSelected'));
    expect(personal, contains('ProgressiveSearchCoordinator('));
    expect(personal, contains("Key('discover-search-nearby')"));
    expect(personal, contains('clearLocation: true'));
    expect(routes, contains('geoSearch: runtime.geoSearch'));
    expect(routes, contains('location: runtime.location'));
  });
  test('Map and Search share criteria, selection and the public route context', () {
    final screens = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final routes = File('lib/features/discovery/discovery_routes.dart')
        .readAsStringSync();
    final presentation = File('lib/features/discovery/discovery_mature_view.dart')
        .readAsStringSync();
    final guest = File('lib/features/guest/guest_screen.dart')
        .readAsStringSync();
    final shell = File('lib/app/app_shell.dart').readAsStringSync();
    final router = File('lib/app/router.dart').readAsStringSync();

    expect(routes, contains('DiscoveryQuery.fromRouteParameters'));
    expect(routes, contains("state.uri.queryParameters['selected']"));
    expect(screens, contains("routeLocation('/discover/map'"));
    expect(screens, contains("routeLocation('/discover/search'"));
    expect(screens, contains('retainedDiscoveryScrollOffset'));
    expect(screens, contains('retainedDiscoveryFocusedCandidate'));
    expect(screens, contains('_pageTokens[page]'));
    expect(presentation, contains('showMapOnCompact'));
    expect(presentation, contains('onCircleTapped'));
    expect(presentation, contains("key: const Key('discover-compact-map')"));
    expect(presentation, contains('onFocusedCandidateChanged'));
    expect(shell, contains('activeExploration'));
    expect(router, contains('publicDiscoveryQuery'));
    expect(guest, contains('initialFilters'));
  });

}
