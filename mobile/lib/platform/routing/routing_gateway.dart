/// Provider-neutral, transient route computation between published coordinates.
/// Geometry and ETA are estimates, never an Activity/Place or Access truth.
class RoutingPoint {
  const RoutingPoint(this.latitude, this.longitude);

  final double latitude;
  final double longitude;

  bool get isValid =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude >= -90 &&
      latitude <= 90 &&
      longitude >= -180 &&
      longitude <= 180;
}

enum RoutingMode { walking, cycling, driving }

class RoutingPath {
  const RoutingPath({
    required this.points,
    required this.distanceMeters,
    required this.durationSeconds,
    required this.mode,
  });

  final List<RoutingPoint> points;
  final double distanceMeters;
  final double durationSeconds;
  final RoutingMode mode;
}

abstract interface class RoutingGateway {
  Future<RoutingPath> directions(
    RoutingPoint origin,
    RoutingPoint destination, {
    RoutingMode mode = RoutingMode.walking,
  });

  void close();
}

class RoutingUnavailable implements Exception {
  const RoutingUnavailable(this.message);
  final String message;

  @override
  String toString() => 'RoutingUnavailable: $message';
}
