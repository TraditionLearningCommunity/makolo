import '../permissions/permission_gateway.dart';
import 'integrated_camera.dart';

enum CameraCapabilityStatus {
  ready,
  cameraDenied,
  cameraSettingsRequired,
  cameraRestricted,
  microphoneDenied,
  microphoneSettingsRequired,
  microphoneRestricted,
  unavailable,
}

class CameraCapabilityResult {
  const CameraCapabilityResult({
    required this.status,
    this.session,
    this.permission,
  });

  final CameraCapabilityStatus status;
  final IntegratedCameraSession? session;
  final PermissionDecision? permission;

  bool get ready =>
      status == CameraCapabilityStatus.ready && session != null;
}

class CameraCapability {
  const CameraCapability({
    required this.permissions,
    required this.camera,
  });

  final PermissionGateway permissions;
  final IntegratedCamera camera;

  Future<CameraCapabilityResult> open({
    MakoloCameraLens preferredLens = MakoloCameraLens.back,
    bool enableAudio = false,
  }) async {
    final cameraPermission = await permissions.requestWhenNeeded(
      MakoloPermission.camera,
    );
    final cameraBlocked = _cameraBlocked(cameraPermission);
    if (cameraBlocked != null) return cameraBlocked;

    if (enableAudio) {
      final microphonePermission = await permissions.requestWhenNeeded(
        MakoloPermission.microphone,
      );
      final microphoneBlocked = _microphoneBlocked(microphonePermission);
      if (microphoneBlocked != null) return microphoneBlocked;
    }

    try {
      return CameraCapabilityResult(
        status: CameraCapabilityStatus.ready,
        session: await camera.open(
          preferredLens: preferredLens,
          enableAudio: enableAudio,
        ),
      );
    } on Object {
      return const CameraCapabilityResult(
        status: CameraCapabilityStatus.unavailable,
      );
    }
  }

  CameraCapabilityResult? _cameraBlocked(PermissionDecision permission) {
    final status = switch (permission) {
      PermissionDecision.granted ||
      PermissionDecision.limited ||
      PermissionDecision.provisional => null,
      PermissionDecision.permanentlyDenied =>
        CameraCapabilityStatus.cameraSettingsRequired,
      PermissionDecision.restricted => CameraCapabilityStatus.cameraRestricted,
      PermissionDecision.denied => CameraCapabilityStatus.cameraDenied,
    };
    if (status == null) return null;
    return CameraCapabilityResult(status: status, permission: permission);
  }

  CameraCapabilityResult? _microphoneBlocked(PermissionDecision permission) {
    final status = switch (permission) {
      PermissionDecision.granted ||
      PermissionDecision.limited ||
      PermissionDecision.provisional => null,
      PermissionDecision.permanentlyDenied =>
        CameraCapabilityStatus.microphoneSettingsRequired,
      PermissionDecision.restricted =>
        CameraCapabilityStatus.microphoneRestricted,
      PermissionDecision.denied => CameraCapabilityStatus.microphoneDenied,
    };
    if (status == null) return null;
    return CameraCapabilityResult(status: status, permission: permission);
  }
}
