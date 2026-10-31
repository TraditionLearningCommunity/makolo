import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/onboarding/onboarding_flow.dart';
import 'package:makolo_mobile/platform/location/discovery_location_context.dart';
import 'package:makolo_mobile/platform/location/location_capability.dart';
import 'package:makolo_mobile/platform/location/location_service.dart';
import 'package:makolo_mobile/platform/permissions/permission_gateway.dart';

class _Permissions implements PermissionGateway {
  _Permissions(this.decision);

  PermissionDecision decision;
  int checks = 0;
  int requests = 0;

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async {
    expect(permission, MakoloPermission.locationWhenInUse);
    checks++;
    return decision;
  }

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async {
    expect(permission, MakoloPermission.locationWhenInUse);
    requests++;
    return decision;
  }

  @override
  Future<bool> openSettings() async => true;
}

class _Location implements LocationService {
  _Location({this.enabled = true});

  final bool enabled;
  int readings = 0;

  @override
  Future<bool> isServiceEnabled() async => enabled;

  @override
  Future<LocationFix> current({
    MakoloLocationAccuracy accuracy = MakoloLocationAccuracy.balanced,
  }) async {
    expect(accuracy, MakoloLocationAccuracy.low);
    readings++;
    return LocationFix(
      latitude: -11.66,
      longitude: 27.47,
      accuracyMeters: 50,
      observedAt: DateTime.utc(2026, 10, 14),
    );
  }

  @override
  Stream<LocationFix> watch({
    LocationTrackingProfile profile = LocationTrackingProfile.balanced,
    bool background = false,
    int? distanceFilterMeters,
    MakoloLocationAccuracy? accuracy,
    Duration? intervalDuration,
  }) => const Stream<LocationFix>.empty();
}

Future<void> _onLocationStep(
  WidgetTester tester,
  LocationCapability capability,
) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: buildMakoloTheme(),
      home: OnboardingFlow(
        isAuthenticated: false,
        location: capability,
        onComplete: (_) async {},
      ),
    ),
  );
  await tester.tap(find.text('Continuer'));
  await tester.pumpAndSettle();
  expect(find.text('Découvrez ce qui vous entoure.'), findsOneWidget);
  expect(find.text('Activer la localisation'), findsOneWidget);
  expect(find.text('Passer'), findsOneWidget);
  expect(find.text('Notifications'), findsNothing);
  expect(find.text('Microphone'), findsNothing);
  expect(find.text('Appareil photo'), findsNothing);
}

void main() {
  setUp(() => DiscoveryLocationContext.update(null));
  tearDown(() => DiscoveryLocationContext.update(null));

  testWidgets('Passer never accesses native permission or position', (
    tester,
  ) async {
    final permissions = _Permissions(PermissionDecision.denied);
    final service = _Location();
    await _onLocationStep(
      tester,
      LocationCapability(permissions: permissions, service: service),
    );
    await tester.tap(find.byKey(const Key('onboarding-location-skip')));
    await tester.pumpAndSettle();
    expect(find.text('Tout commence par une découverte.'), findsOneWidget);
    expect(permissions.checks, 0);
    expect(permissions.requests, 0);
    expect(service.readings, 0);
    expect(DiscoveryLocationContext.current, isNull);
  });

  testWidgets('already granted permission gets one foreground fix', (
    tester,
  ) async {
    final permissions = _Permissions(PermissionDecision.granted);
    final service = _Location();
    await _onLocationStep(
      tester,
      LocationCapability(permissions: permissions, service: service),
    );
    await tester.tap(find.text('Activer la localisation'));
    await tester.pumpAndSettle();
    expect(permissions.checks, 1);
    expect(permissions.requests, 0);
    expect(service.readings, 1);
    expect(DiscoveryLocationContext.current, isNotNull);
    expect(find.text('Tout commence par une découverte.'), findsOneWidget);
  });

  testWidgets('denial keeps Passer available without a position', (
    tester,
  ) async {
    final permissions = _Permissions(PermissionDecision.denied);
    final service = _Location();
    await _onLocationStep(
      tester,
      LocationCapability(permissions: permissions, service: service),
    );
    await tester.tap(find.text('Activer la localisation'));
    await tester.pumpAndSettle();
    expect(permissions.requests, 1);
    expect(service.readings, 0);
    expect(DiscoveryLocationContext.current, isNull);
    expect(find.text('Passer'), findsOneWidget);
    await tester.tap(find.text('Passer'));
    await tester.pumpAndSettle();
    expect(find.text('Tout commence par une découverte.'), findsOneWidget);
  });

  testWidgets('permanent denial never opens another system dialog', (
    tester,
  ) async {
    final permissions = _Permissions(PermissionDecision.permanentlyDenied);
    final service = _Location();
    await _onLocationStep(
      tester,
      LocationCapability(permissions: permissions, service: service),
    );
    await tester.tap(find.text('Activer la localisation'));
    await tester.pumpAndSettle();
    expect(permissions.requests, 0);
    expect(service.readings, 0);
    expect(find.textContaining('réglages Android'), findsOneWidget);
    expect(find.text('Passer'), findsOneWidget);
  });

  testWidgets('disabled location service never creates a fix', (tester) async {
    final permissions = _Permissions(PermissionDecision.granted);
    final service = _Location(enabled: false);
    await _onLocationStep(
      tester,
      LocationCapability(permissions: permissions, service: service),
    );
    await tester.tap(find.text('Activer la localisation'));
    await tester.pumpAndSettle();
    expect(service.readings, 0);
    expect(DiscoveryLocationContext.current, isNull);
    expect(find.textContaining('désactivé'), findsOneWidget);
    expect(find.text('Passer'), findsOneWidget);
  });
}
