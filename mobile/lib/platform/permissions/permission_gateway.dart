import 'package:permission_handler/permission_handler.dart';

enum MakoloPermission {
  camera,
  microphone,
  locationWhenInUse,
  notifications,
}

enum PermissionDecision {
  granted,
  denied,
  permanentlyDenied,
  restricted,
  limited,
  provisional,
}

abstract interface class PermissionGateway {
  Future<PermissionDecision> status(MakoloPermission permission);
  Future<PermissionDecision> request(MakoloPermission permission);
  Future<bool> openSettings();
}

class PermissionHandlerGateway implements PermissionGateway {
  const PermissionHandlerGateway();

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async {
    return _map(await _native(permission).status);
  }

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async {
    return _map(await _native(permission).request());
  }

  @override
  Future<bool> openSettings() => openAppSettings();

  Permission _native(MakoloPermission permission) {
    return switch (permission) {
      MakoloPermission.camera => Permission.camera,
      MakoloPermission.microphone => Permission.microphone,
      MakoloPermission.locationWhenInUse => Permission.locationWhenInUse,
      MakoloPermission.notifications => Permission.notification,
    };
  }

  PermissionDecision _map(PermissionStatus status) {
    if (status.isGranted) return PermissionDecision.granted;
    if (status.isPermanentlyDenied) return PermissionDecision.permanentlyDenied;
    if (status.isRestricted) return PermissionDecision.restricted;
    if (status.isLimited) return PermissionDecision.limited;
    if (status.isProvisional) return PermissionDecision.provisional;
    return PermissionDecision.denied;
  }
}
