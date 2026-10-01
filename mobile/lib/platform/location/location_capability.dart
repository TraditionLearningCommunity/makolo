import 'dart:async';

import '../permissions/permission_gateway.dart';
import 'location_service.dart';

enum LocationCapabilityStatus {
  ready,
  permissionDenied,
  settingsRequired,
  restricted,
  serviceUnavailable,
  disabledByConfiguration,
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
  LocationWatchHandle._({
    required this.profile,
    required this.background,
    this.onStopped,
  });

  final LocationTrackingProfile profile;
  final bool background;
  final void Function()? onStopped;

  StreamSubscription<LocationFix>? _subscription;
  bool _stopped = false;

  bool get stopped => _stopped;

  void attach(StreamSubscription<LocationFix> subscription) {
    if (_subscription != null) {
      throw StateError('Location subscription already attached.');
    }
    if (_stopped) {
      unawaited(subscription.cancel());
      return;
    }
    _subscription = subscription;
  }

  Future<void> stop() async {
    if (_stopped) return;
    _stopped = true;
    final subscription = _subscription;
    _subscription = null;
    if (subscription != null) await subscription.cancel();
    onStopped?.call();
  }

  void markStoppedFromStream() {
    if (_stopped) return;
    _stopped = true;
    _subscription = null;
    onStopped?.call();
  }
}

class LocationWatchResult {
  const LocationWatchResult({
    required this.status,
    this.handle,
    this.permission,
    this.reusedExistingSession = false,
  });

  final LocationCapabilityStatus status;
  final LocationWatchHandle? handle;
  final PermissionDecision? permission;
  final bool reusedExistingSession;

  bool get started =>
      status == LocationCapabilityStatus.ready && handle != null;
}

class LocationCapability {
  LocationCapability({
    required this.permissions,
    required this.service,
    this.backgroundCapabilityEnabled = false,
  });

  final PermissionGateway permissions;
  final LocationService service;
  final bool backgroundCapabilityEnabled;

  LocationWatchHandle? _backgroundSession;

  LocationWatchHandle? get backgroundSession {
    final session = _backgroundSession;
    if (session == null || session.stopped) return null;
    return session;
  }

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
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    LocationTrackingProfile profile = LocationTrackingProfile.balanced,
  }) {
    return foregroundWatch(
      onFix: onFix,
      onError: onError,
      distanceFilterMeters: distanceFilterMeters,
      accuracy: accuracy,
      profile: profile,
    );
  }

  Future<LocationWatchResult> foregroundWatch({
    required void Function(LocationFix fix) onFix,
    void Function(Object error)? onError,
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    LocationTrackingProfile profile = LocationTrackingProfile.balanced,
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

    return _startWatch(
      profile: profile,
      background: false,
      permission: permission,
      onFix: onFix,
      onError: onError,
      distanceFilterMeters: distanceFilterMeters,
      accuracy: accuracy,
    );
  }

  Future<LocationWatchResult> startBackgroundSession({
    required void Function(LocationFix fix) onFix,
    void Function(Object error)? onError,
    LocationTrackingProfile profile = LocationTrackingProfile.active,
  }) async {
    if (!backgroundCapabilityEnabled) {
      return const LocationWatchResult(
        status: LocationCapabilityStatus.disabledByConfiguration,
      );
    }

    final existing = backgroundSession;
    if (existing != null) {
      return LocationWatchResult(
        status: LocationCapabilityStatus.ready,
        handle: existing,
        reusedExistingSession: true,
      );
    }

    final foregroundPermission = await permissions.requestWhenNeeded(
      MakoloPermission.locationWhenInUse,
    );
    final foregroundBlocked = _blocked(foregroundPermission);
    if (foregroundBlocked != null) {
      return LocationWatchResult(
        status: foregroundBlocked.status,
        permission: foregroundBlocked.permission,
      );
    }

    final backgroundPermission = await permissions.requestWhenNeeded(
      MakoloPermission.locationAlways,
    );
    final backgroundBlocked = _blocked(backgroundPermission);
    if (backgroundBlocked != null) {
      return LocationWatchResult(
        status: backgroundBlocked.status,
        permission: backgroundBlocked.permission,
      );
    }

    if (!await service.isServiceEnabled()) {
      return const LocationWatchResult(
        status: LocationCapabilityStatus.serviceUnavailable,
      );
    }

    late final LocationWatchHandle handle;
    handle = LocationWatchHandle._(
      profile: profile,
      background: true,
      onStopped: () {
        if (identical(_backgroundSession, handle)) {
          _backgroundSession = null;
        }
      },
    );
    _backgroundSession = handle;

    final result = _startWatch(
      profile: profile,
      background: true,
      permission: backgroundPermission,
      onFix: onFix,
      onError: onError,
      existingHandle: handle,
    );
    if (!result.started) {
      _backgroundSession = null;
    }
    return result;
  }

  Future<void> stopBackgroundSession() async {
    final session = _backgroundSession;
    _backgroundSession = null;
    await session?.stop();
  }

  LocationWatchResult _startWatch({
    required LocationTrackingProfile profile,
    required bool background,
    required PermissionDecision permission,
    required void Function(LocationFix fix) onFix,
    void Function(Object error)? onError,
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    LocationWatchHandle? existingHandle,
  }) {
    final handle =
        existingHandle ??
        LocationWatchHandle._(profile: profile, background: background);
    try {
      final subscription = service
          .watch(
            profile: profile,
            background: background,
            distanceFilterMeters: distanceFilterMeters,
            accuracy: accuracy,
          )
          .listen(
            onFix,
            onError: (Object error, StackTrace _) {
              handle.markStoppedFromStream();
              onError?.call(error);
            },
            onDone: handle.markStoppedFromStream,
            cancelOnError: true,
          );
      handle.attach(subscription);
      return LocationWatchResult(
        status: LocationCapabilityStatus.ready,
        handle: handle,
        permission: permission,
      );
    } on Object {
      handle.markStoppedFromStream();
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
