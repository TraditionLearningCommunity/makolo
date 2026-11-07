import 'geo_search_gateway.dart';

/// Builds the selected provider adapter outside feature and presentation code.
GeoSearchGateway? createGeoSearchGateway({
  required bool enabled,
  required String provider,
  required String? apiKey,
  Uri? endpoint,
}) {
  if (!enabled) return null;
  final key = apiKey?.trim();
  if (key == null || key.isEmpty) {
    throw ArgumentError('Enabled geocoding requires an API key.');
  }
  if (endpoint == null || endpoint.scheme != 'https') {
    throw ArgumentError(
      'Enabled geocoding requires a configured HTTPS endpoint.',
    );
  }
  return switch (provider.trim().toLowerCase()) {
    'maptiler' => MapTilerGeoSearchGateway(
        apiKey: key,
        endpoint: endpoint,
      ),
    'google_maps' => GoogleMapsGeoSearchGateway(
        apiKey: key,
        endpoint: endpoint,
      ),
    _ => throw ArgumentError.value(
        provider,
        'provider',
        'Unsupported geocoding provider',
      ),
  };
}
