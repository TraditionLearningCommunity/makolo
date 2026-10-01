import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/location/location_capability.dart';
import 'package:makolo_mobile/platform/location/location_service.dart';
import 'package:makolo_mobile/platform/permissions/permission_gateway.dart';

class FakePermissionGateway implements PermissionGateway {
  FakePermissionGateway({
    Map<MakoloPermission, PermissionDecision>? statuses,
    Map<MakoloPermission, PermissionDecision>? requestResults,
  }) : statuses = Map.of(statuses ?? const {}),
       requestResults = Map.of(requestResults ?? const {});

  final Map<MakoloPermission, PermissionDecision> statuses;
  final Map<MakoloPermission, PermissionDecision> requestResults;
  final List<MakoloPermission> statusChecks = [];
  final List<MakoloPermission> requests = [];

  @override
  Future<bool> openSettings() async => true;

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async {
    requests.add(permission);
    final result =
        requestResults[permission] ??
        statuses[permission] ??
        PermissionDecision.denied;
    statuses[permission] = result;
    return result;
  }

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async {
    statusChecks.add(permission);
    return statuses[permission] ?? PermissionDecision.denied;
  }
}

class FakeLocationService implements LocationService {
  FakeLocationService({
    this.enabled = true,
    this.throwOnCurrent = false,
    this.throwOnWatch = false,
  });

  final bool enabled;
  final bool throwOnCurrent;
  final bool throwOnWatch;
  final controller = StreamController<LocationFix>.broadcast();

  int currentCount = 0;
  int watchCount = 0;
  MakoloLocationAccuracy? lastAccuracy;
  LocationTrackingProfile? lastProfile;
  bool? lastBackground;

  @override
  Future<LocationFix> current({
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) async {
    currentCount += 1;
    lastAccuracy = accuracy;
    if (throwOnCurrent) throw StateError('native current failed');
    return LocationFix(
      latitude: -11.66,
      longitude: 27.47,
      accuracyMeters: 20,
      observedAt: DateTime.utc(2026, 9, 30),
    );
  }

  @override
  Future<bool> isServiceEnabled() async => enabled;

  @override
  Stream<LocationFix> watch({
    LocationTrackingProfile profile = LocationTrackingProfile.balanced,
    bool background = false,
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    Duration? intervalDuration,
  }) {
    watchCount += 1;
    lastProfile = profile;
    lastBackground = background;
    lastAccuracy = accuracy;
    if (throwOnWatch) throw StateError('native watch failed');
    return controller.stream;
  }
}

FakePermissionGateway grantedForegroundPermissions() {
  return FakePermissionGateway(
    statuses: const {
      MakoloPermission.locationWhenInUse: PermissionDecision.granted,
    },
  );
}

Future<void> closeService(FakeLocationService service) async {
  await service.controller.close();
}

void main() {
  test('current succeeds with foreground permission already granted', () async {
    final permissions = grantedForegroundPermissions();
    final service = FakeLocationService();
    addTearDown(() => closeService(service));

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
    ).current();

    expect(result.status, LocationCapabilityStatus.ready);
    expect(result.fix, isNotNull);
    expect(service.currentCount, 1);
    expect(service.lastAccuracy, MakoloLocationAccuracy.balanced);
    expect(permissions.requests, isEmpty);
  });

  test('current denied does not touch native current location', () async {
    final permissions = FakePermissionGateway(
      statuses: const {
        MakoloPermission.locationWhenInUse: PermissionDecision.denied,
      },
      requestResults: const {
        MakoloPermission.locationWhenInUse: PermissionDecision.denied,
      },
    );
    final service = FakeLocationService();
    addTearDown(() => closeService(service));

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
    ).current();

    expect(result.status, LocationCapabilityStatus.permissionDenied);
    expect(service.currentCount, 0);
    expect(permissions.requests, [MakoloPermission.locationWhenInUse]);
  });

  test(
    'current permanently denied requires settings without a dialog',
    () async {
      final permissions = FakePermissionGateway(
        statuses: const {
          MakoloPermission.locationWhenInUse:
              PermissionDecision.permanentlyDenied,
        },
      );
      final service = FakeLocationService();
      addTearDown(() => closeService(service));

      final result = await LocationCapability(
        permissions: permissions,
        service: service,
      ).current();

      expect(result.status, LocationCapabilityStatus.settingsRequired);
      expect(service.currentCount, 0);
      expect(permissions.requests, isEmpty);
    },
  );

  test('current reports disabled location service explicitly', () async {
    final permissions = grantedForegroundPermissions();
    final service = FakeLocationService(enabled: false);
    addTearDown(() => closeService(service));

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
    ).current();

    expect(result.status, LocationCapabilityStatus.serviceUnavailable);
    expect(service.currentCount, 0);
  });

  test('current normalizes a native failure', () async {
    final permissions = grantedForegroundPermissions();
    final service = FakeLocationService(throwOnCurrent: true);
    addTearDown(() => closeService(service));

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
    ).current();

    expect(result.status, LocationCapabilityStatus.failed);
  });

  test('foreground watch starts and stop is idempotent', () async {
    final permissions = grantedForegroundPermissions();
    final service = FakeLocationService();
    addTearDown(() => closeService(service));
    final capability = LocationCapability(
      permissions: permissions,
      service: service,
    );

    final result = await capability.foregroundWatch(
      profile: LocationTrackingProfile.balanced,
      onFix: (_) {},
    );

    expect(result.started, isTrue);
    expect(service.watchCount, 1);
    expect(service.lastBackground, isFalse);
    expect(service.lastProfile, LocationTrackingProfile.balanced);
    expect(service.controller.hasListener, isTrue);

    await result.handle!.stop();
    await result.handle!.stop();

    expect(result.handle!.stopped, isTrue);
    expect(service.controller.hasListener, isFalse);
  });

  test('background disabled by config never requests a permission', () async {
    final permissions = FakePermissionGateway();
    final service = FakeLocationService();
    addTearDown(() => closeService(service));

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
      backgroundCapabilityEnabled: false,
    ).startBackgroundSession(onFix: (_) {});

    expect(result.status, LocationCapabilityStatus.disabledByConfiguration);
    expect(permissions.statusChecks, isEmpty);
    expect(permissions.requests, isEmpty);
    expect(service.watchCount, 0);
  });

  test(
    'background permission flow requests foreground before always',
    () async {
      final permissions = FakePermissionGateway(
        statuses: const {
          MakoloPermission.locationWhenInUse: PermissionDecision.denied,
          MakoloPermission.locationAlways: PermissionDecision.denied,
        },
        requestResults: const {
          MakoloPermission.locationWhenInUse: PermissionDecision.granted,
          MakoloPermission.locationAlways: PermissionDecision.granted,
        },
      );
      final service = FakeLocationService();
      addTearDown(() => closeService(service));
      final capability = LocationCapability(
        permissions: permissions,
        service: service,
        backgroundCapabilityEnabled: true,
      );

      final result = await capability.startBackgroundSession(onFix: (_) {});

      expect(result.started, isTrue);
      expect(permissions.requests, [
        MakoloPermission.locationWhenInUse,
        MakoloPermission.locationAlways,
      ]);
      expect(service.lastBackground, isTrue);
      expect(service.lastProfile, LocationTrackingProfile.active);

      await capability.stopBackgroundSession();
    },
  );

  test('background permission denial does not start native tracking', () async {
    final permissions = FakePermissionGateway(
      statuses: const {
        MakoloPermission.locationWhenInUse: PermissionDecision.granted,
        MakoloPermission.locationAlways: PermissionDecision.denied,
      },
      requestResults: const {
        MakoloPermission.locationAlways: PermissionDecision.denied,
      },
    );
    final service = FakeLocationService();
    addTearDown(() => closeService(service));

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
      backgroundCapabilityEnabled: true,
    ).startBackgroundSession(onFix: (_) {});

    expect(result.status, LocationCapabilityStatus.permissionDenied);
    expect(permissions.requests, [MakoloPermission.locationAlways]);
    expect(service.watchCount, 0);
  });

  test('background session stop clears the active session', () async {
    final permissions = FakePermissionGateway(
      statuses: const {
        MakoloPermission.locationWhenInUse: PermissionDecision.granted,
        MakoloPermission.locationAlways: PermissionDecision.granted,
      },
    );
    final service = FakeLocationService();
    addTearDown(() => closeService(service));
    final capability = LocationCapability(
      permissions: permissions,
      service: service,
      backgroundCapabilityEnabled: true,
    );

    final result = await capability.startBackgroundSession(onFix: (_) {});
    expect(result.started, isTrue);
    expect(capability.backgroundSession, same(result.handle));
    expect(service.controller.hasListener, isTrue);

    await capability.stopBackgroundSession();
    await capability.stopBackgroundSession();

    expect(capability.backgroundSession, isNull);
    expect(result.handle!.stopped, isTrue);
    expect(service.controller.hasListener, isFalse);
  });

  test('double background start reuses one native session', () async {
    final permissions = FakePermissionGateway(
      statuses: const {
        MakoloPermission.locationWhenInUse: PermissionDecision.granted,
        MakoloPermission.locationAlways: PermissionDecision.granted,
      },
    );
    final service = FakeLocationService();
    addTearDown(() => closeService(service));
    final capability = LocationCapability(
      permissions: permissions,
      service: service,
      backgroundCapabilityEnabled: true,
    );

    final first = await capability.startBackgroundSession(onFix: (_) {});
    final second = await capability.startBackgroundSession(onFix: (_) {});

    expect(first.started, isTrue);
    expect(second.started, isTrue);
    expect(second.reusedExistingSession, isTrue);
    expect(second.handle, same(first.handle));
    expect(service.watchCount, 1);

    await capability.stopBackgroundSession();
  });

  test(
    'native start failure does not leave a ghost background session',
    () async {
      final permissions = FakePermissionGateway(
        statuses: const {
          MakoloPermission.locationWhenInUse: PermissionDecision.granted,
          MakoloPermission.locationAlways: PermissionDecision.granted,
        },
      );
      final service = FakeLocationService(throwOnWatch: true);
      addTearDown(() => closeService(service));
      final capability = LocationCapability(
        permissions: permissions,
        service: service,
        backgroundCapabilityEnabled: true,
      );

      final result = await capability.startBackgroundSession(onFix: (_) {});

      expect(result.status, LocationCapabilityStatus.failed);
      expect(capability.backgroundSession, isNull);
    },
  );

  test('stream error stops and clears the background session', () async {
    final permissions = FakePermissionGateway(
      statuses: const {
        MakoloPermission.locationWhenInUse: PermissionDecision.granted,
        MakoloPermission.locationAlways: PermissionDecision.granted,
      },
    );
    final service = FakeLocationService();
    addTearDown(() => closeService(service));
    final errors = <Object>[];
    final capability = LocationCapability(
      permissions: permissions,
      service: service,
      backgroundCapabilityEnabled: true,
    );

    final result = await capability.startBackgroundSession(
      onFix: (_) {},
      onError: errors.add,
    );
    service.controller.addError(StateError('permission revoked'));
    await Future<void>.delayed(Duration.zero);

    expect(errors, hasLength(1));
    expect(result.handle!.stopped, isTrue);
    expect(capability.backgroundSession, isNull);
  });

  test('ambient foreground profile remains distinct from background', () async {
    final permissions = grantedForegroundPermissions();
    final service = FakeLocationService();
    addTearDown(() => closeService(service));
    final capability = LocationCapability(
      permissions: permissions,
      service: service,
    );

    final result = await capability.foregroundWatch(
      profile: LocationTrackingProfile.ambient,
      onFix: (_) {},
    );

    expect(result.started, isTrue);
    expect(service.lastProfile, LocationTrackingProfile.ambient);
    expect(service.lastBackground, isFalse);

    await result.handle!.stop();
  });
}
