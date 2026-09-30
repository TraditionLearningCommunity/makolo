import 'package:geolocator/geolocator.dart';

enum MakoloLocationAccuracy { low, balanced, high }

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

  Future<LocationFix> current({
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  });

  Stream<LocationFix> watch({
    int distanceFilterMeters = 25,
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  });
}

class GeolocatorLocationService implements LocationService {
  const GeolocatorLocationService();

  @override
  Future<bool> isServiceEnabled() => Geolocator.isLocationServiceEnabled();

  @override
  Future<LocationFix> current({
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) async {
    final position = await Geolocator.getCurrentPosition(
      locationSettings: LocationSettings(accuracy: _accuracy(accuracy)),
    );
    return _fix(position);
  }

  @override
  Stream<LocationFix> watch({
    int distanceFilterMeters = 25,
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) {
    return Geolocator.getPositionStream(
      locationSettings: LocationSettings(
        accuracy: _accuracy(accuracy),
        distanceFilter: distanceFilterMeters,
      ),
    ).map(_fix);
  }

  LocationAccuracy _accuracy(MakoloLocationAccuracy accuracy) {
    return switch (accuracy) {
      MakoloLocationAccuracy.low => LocationAccuracy.low,
      MakoloLocationAccuracy.balanced => LocationAccuracy.medium,
      MakoloLocationAccuracy.high => LocationAccuracy.high,
    };
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
