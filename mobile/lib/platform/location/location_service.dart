import 'package:geolocator/geolocator.dart';

class LocationFix {
  const LocationFix({
    required this.latitude,
    required this.longitude,
    required this.accuracyMeters,
    required this.observedAt,
    this.altitudeMeters,
    this.speedMetersPerSecond,
    this.headingDegrees,
  });

  final double latitude;
  final double longitude;
  final double accuracyMeters;
  final DateTime observedAt;
  final double? altitudeMeters;
  final double? speedMetersPerSecond;
  final double? headingDegrees;
}

abstract interface class LocationService {
  Future<bool> isServiceEnabled();
  Future<LocationFix> current();
  Stream<LocationFix> watch({int distanceFilterMeters = 10});
}

class GeolocatorLocationService implements LocationService {
  const GeolocatorLocationService();

  @override
  Future<bool> isServiceEnabled() => Geolocator.isLocationServiceEnabled();

  @override
  Future<LocationFix> current() async {
    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
    );
    return _fix(position);
  }

  @override
  Stream<LocationFix> watch({int distanceFilterMeters = 10}) {
    return Geolocator.getPositionStream(
      locationSettings: LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: distanceFilterMeters,
      ),
    ).map(_fix);
  }

  LocationFix _fix(Position position) {
    return LocationFix(
      latitude: position.latitude,
      longitude: position.longitude,
      accuracyMeters: position.accuracy,
      observedAt: position.timestamp,
      altitudeMeters: position.altitude,
      speedMetersPerSecond: position.speed,
      headingDegrees: position.heading,
    );
  }
}
