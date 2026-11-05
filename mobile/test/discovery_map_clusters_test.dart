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
      {'location_key': 'airport'},
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
}
