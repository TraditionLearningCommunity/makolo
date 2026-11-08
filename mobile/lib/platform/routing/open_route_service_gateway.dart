import 'package:dio/dio.dart';

import 'routing_gateway.dart';

/// Optional HeiGIT OpenRouteService Standard adapter.
/// A credential must be supplied by an approved runtime; the free public
/// service is quota-limited, so it is never activated implicitly.
class OpenRouteServiceGateway implements RoutingGateway {
  OpenRouteServiceGateway({required String apiKey, Uri? endpoint, Dio? dio})
    : _key = apiKey.trim(),
      _endpoint =
          endpoint ??
          Uri.parse('https://api.heigit.org/openrouteservice/v2/directions'),
      _dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: const Duration(seconds: 5),
              receiveTimeout: const Duration(seconds: 10),
            ),
          ) {
    if (_key.isEmpty ||
        _endpoint.scheme != 'https' ||
        _endpoint.host.isEmpty ||
        _endpoint.hasQuery ||
        _endpoint.hasFragment ||
        _endpoint.userInfo.isNotEmpty) {
      throw ArgumentError('Routing requires approved HTTPS configuration.');
    }
  }

  final String _key;
  final Uri _endpoint;
  final Dio _dio;

  @override
  void close() => _dio.close(force: true);

  @override
  Future<RoutingPath> directions(
    RoutingPoint origin,
    RoutingPoint destination, {
    RoutingMode mode = RoutingMode.walking,
  }) async {
    if (!origin.isValid ||
        !destination.isValid ||
        (origin.latitude == destination.latitude &&
            origin.longitude == destination.longitude)) {
      throw ArgumentError('Routing requires two distinct valid coordinates.');
    }
    final profile = switch (mode) {
      RoutingMode.walking => 'foot-walking',
      RoutingMode.cycling => 'cycling-regular',
      RoutingMode.driving => 'driving-car',
    };
    final uri = _endpoint.replace(
      pathSegments: [
        ..._endpoint.pathSegments.where((segment) => segment.isNotEmpty),
        profile,
        'geojson',
      ],
    );
    try {
      final response = await _dio.postUri<Map<String, dynamic>>(
        uri,
        data: {
          'coordinates': [
            [origin.longitude, origin.latitude],
            [destination.longitude, destination.latitude],
          ],
        },
        options: Options(
          headers: {'Authorization': _key, 'Content-Type': 'application/json'},
        ),
      );
      final features = response.data?['features'];
      if (features is! List || features.isEmpty || features.first is! Map) {
        throw const FormatException('No route features');
      }
      final feature = features.first as Map;
      final properties = feature['properties'];
      final summary = properties is Map ? properties['summary'] : null;
      final geometry = feature['geometry'];
      final coordinates = geometry is Map ? geometry['coordinates'] : null;
      final distance = summary is Map ? summary['distance'] : null;
      final duration = summary is Map ? summary['duration'] : null;
      if (distance is! num ||
          duration is! num ||
          !distance.toDouble().isFinite ||
          !duration.toDouble().isFinite ||
          distance < 0 ||
          duration < 0 ||
          coordinates is! List ||
          coordinates.length < 2) {
        throw const FormatException('Invalid route summary');
      }
      final points = <RoutingPoint>[];
      for (final coordinate in coordinates) {
        if (coordinate is! List ||
            coordinate.length < 2 ||
            coordinate[0] is! num ||
            coordinate[1] is! num) {
          throw const FormatException('Invalid route geometry');
        }
        // GeoJSON is [longitude, latitude]; Flutter is [latitude, longitude].
        final point = RoutingPoint(
          (coordinate[1] as num).toDouble(),
          (coordinate[0] as num).toDouble(),
        );
        if (!point.isValid) throw const FormatException('Invalid coordinates');
        points.add(point);
      }
      return RoutingPath(
        points: List.unmodifiable(points),
        distanceMeters: distance.toDouble(),
        durationSeconds: duration.toDouble(),
        mode: mode,
      );
    } on DioException {
      // Never surface the API key, request headers, or raw provider response.
      throw const RoutingUnavailable('Itinéraire temporairement indisponible.');
    } on FormatException {
      throw const RoutingUnavailable('Réponse d’itinéraire invalide.');
    } on TypeError {
      throw const RoutingUnavailable('Réponse d’itinéraire invalide.');
    }
  }
}
