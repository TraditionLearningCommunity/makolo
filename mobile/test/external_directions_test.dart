import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/maps/external_directions.dart';

void main() {
  test(
    'Google Maps uses universal directions without the user GPS location',
    () {
      final uri = ExternalDirections.googleMaps(-29.315, 27.483);
      expect(uri.scheme, 'https');
      expect(uri.host, 'www.google.com');
      expect(uri.path, '/maps/dir/');
      expect(uri.queryParameters['api'], '1');
      expect(uri.queryParameters['destination'], '-29.315,27.483');
      expect(uri.queryParameters['dir_action'], 'navigate');
      expect(uri.queryParameters.containsKey('origin'), isFalse);
      expect(uri.queryParameters.containsKey('key'), isFalse);
    },
  );

  test('invalid destinations are rejected before opening navigation', () {
    for (final point in [
      (double.nan, 10.0),
      (91.0, 0.0),
      (0.0, -181.0),
      (double.infinity, 20.0),
    ]) {
      expect(ExternalDirections.valid(point.$1, point.$2), isFalse);
      expect(
        () => ExternalDirections.googleMaps(point.$1, point.$2),
        throwsArgumentError,
      );
    }
  });
}
