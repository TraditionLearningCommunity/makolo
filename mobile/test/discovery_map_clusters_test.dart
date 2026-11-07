import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/maps/discovery_map_controller.dart';

void main() {
  test('Carte GeoJSON uses only published location coordinates and keys', () {
    final payload = DiscoveryMapController.geoJsonForPins(const [
      DiscoveryMapPin(-11.6647, 27.4794, locationKey: 'airport'),
      DiscoveryMapPin(-11.6599, 27.4801, locationKey: 'city'),
    ]);
    expect(payload['type'], 'FeatureCollection');
    final features = payload['features'] as List;
    expect(features, hasLength(2));
    expect(
      (features.first as Map)['properties'],
      {
        'location_key': 'airport',
        'opportunity_count': 1,
        'selected': false,
        'symbol': '',
      },
    );
    expect(
      ((features.first as Map)['geometry'] as Map)['coordinates'],
      [27.4794, -11.6647],
      reason: 'GeoJSON is longitude-first, unlike the public LatLng UI',
    );
    expect(
      ((features.last as Map)['geometry'] as Map)['coordinates'],
      [27.4801, -11.6599],
    );
    expect(
      (features.first as Map).keys,
      containsAll(['type', 'properties', 'geometry']),
    );
    expect((features.first as Map).containsKey('owner'), isFalse);
    expect((features.first as Map).containsKey('actions'), isFalse);
  });

  test('selected markers carry only public presentation attributes', () {
    final payload = DiscoveryMapController.geoJsonForPins(const [
      DiscoveryMapPin(
        -11.66, 27.48,
        locationKey: 'location-public',
        selected: true,
        opportunityCount: 1,
        symbol: '★',
      ),
      DiscoveryMapPin(
        -11.67, 27.49,
        locationKey: 'location-shared',
        opportunityCount: 26,
      ),
    ]);
    final features = payload['features'] as List;
    final first = (features.first as Map)['properties'] as Map;
    final second = (features.last as Map)['properties'] as Map;
    expect(first['selected'], isTrue);
    expect(first['symbol'], '★');
    expect(second['selected'], isFalse);
    expect(second['opportunity_count'], 26);
    expect(second['symbol'], '');
    expect(first.keys, isNot(contains('candidate_id')));
    expect(first.keys, isNot(contains('owner')));
    expect(first.keys, isNot(contains('permission')));
  });
}
