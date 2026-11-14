import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/maps/discovery_map_controller.dart';

void main() {
  test('one location may represent many admitted opportunities', () {
    final geo = DiscoveryMapController.geoJsonForPins(const [
      DiscoveryMapPin(
        -11.66,
        27.48,
        locationKey: 'place-a',
        opportunityCount: 27,
      ),
      DiscoveryMapPin(-11.67, 27.49, locationKey: 'place-b'),
    ]);
    final features = geo['features'] as List;
    expect(features.length, 2);
    final first = features.first as Map;
    final props = first['properties'] as Map;
    expect(props['location_key'], 'place-a');
    expect(props['opportunity_count'], 27);
    expect((features.last as Map)['properties']['opportunity_count'], 1);
    expect((first['geometry'] as Map)['coordinates'], [27.48, -11.66]);
  });

  test('Map markers carry no profile, title, secret or private data', () {
    final feature =
        (DiscoveryMapController.geoJsonForPins(const [
                      DiscoveryMapPin(-11.66, 27.48, opportunityCount: 4),
                    ])['features']
                    as List)
                .single
            as Map;
    expect((feature['properties'] as Map).keys.toSet(), {
      'location_key',
      'opportunity_count',
      'selected',
      'symbol',
    });
  });
}
