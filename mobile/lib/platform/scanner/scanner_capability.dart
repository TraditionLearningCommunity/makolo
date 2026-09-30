import '../permissions/permission_gateway.dart';

enum ScannerCapabilityStatus {
  ready,
  permissionDenied,
  settingsRequired,
  restricted,
}

class ScannerCapabilityResult {
  const ScannerCapabilityResult({
    required this.status,
    required this.permission,
  });

  final ScannerCapabilityStatus status;
  final PermissionDecision permission;

  bool get ready => status == ScannerCapabilityStatus.ready;
}

class ScannerCapability {
  const ScannerCapability(this.permissions);

  final PermissionGateway permissions;

  Future<ScannerCapabilityResult> prepare() async {
    final permission = await permissions.requestWhenNeeded(
      MakoloPermission.camera,
    );
    final status = switch (permission) {
      PermissionDecision.granted ||
      PermissionDecision.limited ||
      PermissionDecision.provisional => ScannerCapabilityStatus.ready,
      PermissionDecision.permanentlyDenied =>
        ScannerCapabilityStatus.settingsRequired,
      PermissionDecision.restricted => ScannerCapabilityStatus.restricted,
      PermissionDecision.denied => ScannerCapabilityStatus.permissionDenied,
    };
    return ScannerCapabilityResult(status: status, permission: permission);
  }
}
