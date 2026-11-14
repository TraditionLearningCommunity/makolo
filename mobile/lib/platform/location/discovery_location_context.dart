import 'location_service.dart';

/// Optional device context for Discovery; never a geographic search filter.
/// Kept only in process memory, not in a Profile or global business model.
class DiscoveryLocationContext {
  DiscoveryLocationContext._();

  static LocationFix? _fix;

  static LocationFix? get current => _fix;

  static void update(LocationFix? fix) {
    _fix = fix;
  }

  static Map<String, String> get parameters {
    final fix = _fix;
    if (fix == null) return const {};
    return {
      'client_lat': fix.latitude.toString(),
      'client_lon': fix.longitude.toString(),
      'client_accuracy_m': fix.accuracyMeters.toString(),
      'client_observed_at': fix.observedAt.toUtc().toIso8601String(),
    };
  }
}
