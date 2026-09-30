import 'dart:async';

import '../permissions/permission_gateway.dart';
import 'location_service.dart';

enum LocationCapabilityStatus {
  ready,
  permissionDenied,
  settingsRequired,
  restricted,
  serviceUnavailable,
  failed,
}

class LocationCapabilityResult {
  const LocationCapabilityResult({
    required this.status,
    this.fix,
    this.permission,
  });

  final LocationCapabilityStatus status;
  final LocationFix? fix;
  final PermissionDecision? permission;

  bool get available => status == LocationCapabilityStatus.ready;
}

class LocationWatchHandle {
  LocationWatchHandle(this._subscription);

  final StreamSubscription<LocationFix> _subscription;
  bool _stopped = false;

  bool get stopped => _stopped;

  Future<void> stop() async {
    if (_stopped) return;
    _stopped = true;
    await _subscription.cancel();
  }
}

class LocationWatchResult {
  const LocationWatchResult({
    required this.status,
    this.handle,
    this.permission,
  });

  final LocationCapabilityStatus status;
  final LocationWatchHandle? handle;
  final PermissionDecision? permission;

  bool get started =>
      status == LocationCapabilityStatus.ready && handle != null;
}

class LocationCapability {
  const LocationCapability({required this.permissions, required this.service});

  final PermissionGateway permissions;
  final LocationService service;

  Future<LocationCapabilityResult> current({
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) async {
    final permission = await permissions.requestWhenNeeded(
      MakoloPermission.locationWhenInUse,
    );
    final blocked = _blocked(permission);
    if (blocked != null) return blocked;

    if (!await service.isServiceEnabled()) {
      return const LocationCapabilityResult(
        status: LocationCapabilityStatus.serviceUnavailable,
      );
    }

    try {
      return LocationCapabilityResult(
        status: LocationCapabilityStatus.ready,
        fix: await service.current(accuracy: accuracy),
        permission: permission,
      );
    } on Object {
      return LocationCapabilityResult(
        status: LocationCapabilityStatus.failed,
        permission: permission,
      );
    }
  }

  Future<LocationWatchResult> watch({
    required void Function(LocationFix fix) onFix,
    void Function(Object error)? onError,
    int distanceFilterMeters = 25,
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) async {
    final permission = await permissions.requestWhenNeeded(
      MakoloPermission.locationWhenInUse,
    );
    final blocked = _blocked(permission);
    if (blocked != null) {
      return LocationWatchResult(
        status: blocked.status,
        permission: blocked.permission,
      );
    }

    if (!await service.isServiceEnabled()) {
      return const LocationWatchResult(
        status: LocationCapabilityStatus.serviceUnavailable,
      );
    }

    try {
      final subscription = service
          .watch(distanceFilterMeters: distanceFilterMeters, accuracy: accuracy)
          .listen(
            onFix,
            onError: onError == null
                ? null
                : (Object error, StackTrace _) => onError(error),
          );
      return LocationWatchResult(
        status: LocationCapabilityStatus.ready,
        handle: LocationWatchHandle(subscription),
        permission: permission,
      );
    } on Object {
      return LocationWatchResult(
        status: LocationCapabilityStatus.failed,
        permission: permission,
      );
    }
  }

  LocationCapabilityResult? _blocked(PermissionDecision permission) {
    final status = switch (permission) {
      PermissionDecision.permanentlyDenied =>
        LocationCapabilityStatus.settingsRequired,
      PermissionDecision.restricted => LocationCapabilityStatus.restricted,
      PermissionDecision.granted ||
      PermissionDecision.limited ||
      PermissionDecision.provisional => null,
      PermissionDecision.denied => LocationCapabilityStatus.permissionDenied,
    };
    if (status == null) return null;
    return LocationCapabilityResult(status: status, permission: permission);
  }
}
