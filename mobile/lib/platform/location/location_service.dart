import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

enum MakoloLocationAccuracy { low, balanced, high }

enum LocationTrackingProfile { ambient, balanced, active }

class LocationTrackingPolicy {
  const LocationTrackingPolicy({
    required this.accuracy,
    required this.distanceFilterMeters,
    required this.intervalDuration,
  });

  final MakoloLocationAccuracy accuracy;
  final int distanceFilterMeters;
  final Duration intervalDuration;

  static const ambient = LocationTrackingPolicy(
    accuracy: MakoloLocationAccuracy.low,
    distanceFilterMeters: 250,
    intervalDuration: Duration(minutes: 2),
  );

  static const balanced = LocationTrackingPolicy(
    accuracy: MakoloLocationAccuracy.balanced,
    distanceFilterMeters: 50,
    intervalDuration: Duration(seconds: 30),
  );

  static const active = LocationTrackingPolicy(
    accuracy: MakoloLocationAccuracy.high,
    distanceFilterMeters: 10,
    intervalDuration: Duration(seconds: 5),
  );

  static LocationTrackingPolicy forProfile(LocationTrackingProfile profile) {
    return switch (profile) {
      LocationTrackingProfile.ambient => ambient,
      LocationTrackingProfile.balanced => balanced,
      LocationTrackingProfile.active => active,
    };
  }
}

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
    LocationTrackingProfile profile = LocationTrackingProfile.balanced,
    bool background = false,
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    Duration? intervalDuration,
  });
}

class GeolocatorLocationService implements LocationService {
  const GeolocatorLocationService();

  static const _backgroundNotification = ForegroundNotificationConfig(
    notificationTitle: 'Makolo — action en cours',
    notificationText: 'Localisation active pour poursuivre cette action.',
    notificationChannelName: 'Localisation Makolo',
    enableWakeLock: false,
    enableWifiLock: false,
    setOngoing: true,
  );

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
    LocationTrackingProfile profile = LocationTrackingProfile.balanced,
    bool background = false,
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    Duration? intervalDuration,
  }) {
    final policy = LocationTrackingPolicy.forProfile(profile);
    final effectiveAccuracy = accuracy ?? policy.accuracy;
    final effectiveDistance =
        distanceFilterMeters ?? policy.distanceFilterMeters;
    final effectiveInterval = intervalDuration ?? policy.intervalDuration;

    final LocationSettings settings;
    if (defaultTargetPlatform == TargetPlatform.android) {
      settings = AndroidSettings(
        accuracy: _accuracy(effectiveAccuracy),
        distanceFilter: effectiveDistance,
        intervalDuration: effectiveInterval,
        foregroundNotificationConfig: background
            ? _backgroundNotification
            : null,
      );
    } else {
      settings = LocationSettings(
        accuracy: _accuracy(effectiveAccuracy),
        distanceFilter: effectiveDistance,
      );
    }

    return Geolocator.getPositionStream(locationSettings: settings).map(_fix);
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
