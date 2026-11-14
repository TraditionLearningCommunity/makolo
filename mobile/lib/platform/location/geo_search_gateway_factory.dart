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
  final configuredEndpoint = endpoint;
  if (configuredEndpoint == null || configuredEndpoint.scheme != 'https') {
    throw ArgumentError(
      'Enabled geocoding requires a configured HTTPS endpoint.',
    );
  }
  return switch (provider.trim().toLowerCase()) {
    'maptiler' => MapTilerGeoSearchGateway(
      apiKey: key,
      endpoint: configuredEndpoint,
    ),
    'google_maps' => GoogleMapsGeoSearchGateway(
      apiKey: key,
      endpoint: configuredEndpoint,
    ),
    _ => throw ArgumentError.value(
      provider,
      'provider',
      'Unsupported geocoding provider',
    ),
  };
}
