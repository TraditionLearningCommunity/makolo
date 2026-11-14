import 'package:dio/dio.dart';

import 'open_route_service_gateway.dart';
import 'routing_gateway.dart';

/// Optional composition boundary. No second map renderer or routing UI.
RoutingGateway? createRoutingGateway({
  required bool enabled,
  String provider = 'openrouteservice',
  String? apiKey,
  Uri? endpoint,
  Dio? dio,
}) {
  if (!enabled) return null;
  if (provider.trim().toLowerCase() != 'openrouteservice') {
    throw ArgumentError.value(
      provider,
      'provider',
      'Unsupported routing provider',
    );
  }
  final key = apiKey?.trim();
  if (key == null || key.isEmpty) {
    throw ArgumentError('Enabled routing requires an approved API key.');
  }
  return OpenRouteServiceGateway(apiKey: key, endpoint: endpoint, dio: dio);
}
