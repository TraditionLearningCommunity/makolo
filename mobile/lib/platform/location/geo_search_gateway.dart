import 'package:dio/dio.dart';

/// One ephemeral geographic suggestion. Never a Makolo Place or Zone record.
class GeoSuggestion {
  const GeoSuggestion({
    required this.id,
    required this.label,
    required this.longitude,
    required this.latitude,
    required this.source,
    this.kind,
  });

  final String id;
  final String label;
  final double longitude;
  final double latitude;
  final String source;
  final String? kind;
}

/// Cancellation contract: presentation never handles Dio directly.
class GeoSearchCancellation {
  final CancelToken _token = CancelToken();

  bool get isCancelled => _token.isCancelled;

  void cancel() => _token.cancel('outdated suggestion');
}

abstract interface class GeoSearchGateway {
  /// A caller owns typing debounce and cancellation. No GPS is sent implicitly.
  Future<List<GeoSuggestion>> suggest(
    String query, {
    String language = 'fr',
    int limit = 5,
    GeoSearchCancellation? cancelToken,
  });
}

class GeoSearchException implements Exception {
  const GeoSearchException(this.message);
  final String message;

  @override
  String toString() => 'GeoSearchException: $message';
}

/// MapTiler forward geocoding adapter, opt-in until the account authorizes it.
/// The token is injected from approved client runtime configuration only.
class MapTilerGeoSearchGateway implements GeoSearchGateway {
  MapTilerGeoSearchGateway({required String apiKey, Dio? dio, Uri? endpoint})
    : _key = apiKey,
      _endpoint = endpoint ?? Uri.parse('https://api.maptiler.com/geocoding/'),
      _dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: const Duration(seconds: 5),
              receiveTimeout: const Duration(seconds: 7),
            ),
          ) {
    if (_key.trim().isEmpty || _endpoint.scheme != 'https') {
      throw ArgumentError(
        'MapTiler geocoding requires approved HTTPS configuration.',
      );
    }
  }

  final String _key;
  final Uri _endpoint;
  final Dio _dio;

  @override
  Future<List<GeoSuggestion>> suggest(
    String query, {
    String language = 'fr',
    int limit = 5,
    GeoSearchCancellation? cancelToken,
  }) async {
    final text = query.trim();
    if (text.isEmpty) return const [];
    final effectiveLimit = limit.clamp(1, 10);
    final uri = _endpoint.replace(
      pathSegments: [
        ..._endpoint.pathSegments.where((segment) => segment.isNotEmpty),
        '$text.json',
      ],
      queryParameters: {
        'key': _key,
        'autocomplete': 'true',
        'limit': '$effectiveLimit',
        'language': language,
      },
    );
    try {
      final response = await _dio.getUri<Map<String, dynamic>>(
        uri,
        cancelToken: cancelToken?._token,
      );
      final features = response.data?['features'];
      if (features is! List) throw const FormatException('Missing features');
      final output = <GeoSuggestion>[];
      for (final raw in features) {
        if (raw is! Map) continue;
        final item = Map<String, dynamic>.from(raw);
        final center = item['center'];
        final name = item['place_name'];
        final id = item['id'];
        if (center is! List ||
            center.length < 2 ||
            center[0] is! num ||
            center[1] is! num ||
            name is! String ||
            name.trim().isEmpty ||
            id is! String) {
          continue;
        }
        final lon = (center[0] as num).toDouble();
        final lat = (center[1] as num).toDouble();
        if (!lon.isFinite ||
            !lat.isFinite ||
            lon < -180 ||
            lon > 180 ||
            lat < -90 ||
            lat > 90) {
          continue;
        }
        final types = item['place_type'];
        output.add(
          GeoSuggestion(
            id: id,
            label: name,
            longitude: lon,
            latitude: lat,
            source: 'maptiler',
            kind: types is List && types.isNotEmpty
                ? types.first.toString()
                : null,
          ),
        );
      }
      return List.unmodifiable(output);
    } on DioException catch (error) {
      if (CancelToken.isCancel(error)) rethrow;
      throw const GeoSearchException(
        'Geographic suggestions are temporarily unavailable.',
      );
    } on FormatException {
      throw const GeoSearchException('Invalid geographic search response.');
    } on TypeError {
      throw const GeoSearchException('Invalid geographic search response.');
    }
  }
}
