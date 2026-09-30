import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/location/location_capability.dart';
import 'package:makolo_mobile/platform/location/location_service.dart';
import 'package:makolo_mobile/platform/permissions/permission_gateway.dart';

class FakePermissionGateway implements PermissionGateway {
  FakePermissionGateway(this.decision);

  PermissionDecision decision;
  int requestCount = 0;

  @override
  Future<bool> openSettings() async => true;

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async {
    requestCount += 1;
    return decision;
  }

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async =>
      decision;
}

class FakeLocationService implements LocationService {
  FakeLocationService({this.enabled = true});

  final bool enabled;
  final controller = StreamController<LocationFix>();
  int currentCount = 0;
  int watchCount = 0;
  MakoloLocationAccuracy? lastAccuracy;

  @override
  Future<LocationFix> current({
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) async {
    currentCount += 1;
    lastAccuracy = accuracy;
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
    int distanceFilterMeters = 25,
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) {
    watchCount += 1;
    lastAccuracy = accuracy;
    return controller.stream;
  }
}

void main() {
  test('denied location does not touch the native service', () async {
    final permissions = FakePermissionGateway(
      PermissionDecision.permanentlyDenied,
    );
    final service = FakeLocationService();

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
    ).current();

    expect(result.status, LocationCapabilityStatus.settingsRequired);
    expect(service.currentCount, 0);
  });

  test('current location uses balanced accuracy by default', () async {
    final permissions = FakePermissionGateway(PermissionDecision.granted);
    final service = FakeLocationService();

    final result = await LocationCapability(
      permissions: permissions,
      service: service,
    ).current();

    expect(result.available, isTrue);
    expect(service.lastAccuracy, MakoloLocationAccuracy.balanced);
  });

  test('location watch is explicitly stoppable', () async {
    final permissions = FakePermissionGateway(PermissionDecision.granted);
    final service = FakeLocationService();
    final capability = LocationCapability(
      permissions: permissions,
      service: service,
    );

    final result = await capability.watch(onFix: (_) {});
    expect(result.started, isTrue);
    expect(service.controller.hasListener, isTrue);

    await result.handle!.stop();
    expect(result.handle!.stopped, isTrue);
    expect(service.controller.hasListener, isFalse);
    await service.controller.close();
  });
}
