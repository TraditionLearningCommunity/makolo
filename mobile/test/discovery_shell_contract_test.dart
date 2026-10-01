import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Discover root has no nested toolbar or permanent search field', () {
    final source = File(
      'lib/features/discovery/discovery_screens.dart',
    ).readAsStringSync();
    final rootEnd = source.indexOf('class DiscoverySearchScreen');
    final root = source.substring(0, rootEnd);

    expect(root, isNot(contains('appBar:')));
    expect(root, isNot(contains('SearchBar(')));
    expect(
      source,
      isNot(contains('Le runtime Mobile ne fournit pas encore de style MapLibre')),
    );
    expect(source, isNot(contains('aucun fournisseur n’est inventé')));
  });

  test('Discover map uses the configured MapLibre runtime', () {
    final source = File(
      'lib/features/discovery/discovery_screens.dart',
    ).readAsStringSync();
    final routes = File(
      'lib/features/discovery/discovery_routes.dart',
    ).readAsStringSync();

    expect(source, contains('ConfiguredMakoloMapView('));
    expect(routes, contains('mapConfig: runtime.mapConfig'));
    expect(routes, contains("path: '/discover/map'"));
  });
}
