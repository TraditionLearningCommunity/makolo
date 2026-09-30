import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/camera/camera_capability.dart';
import 'package:makolo_mobile/platform/camera/integrated_camera.dart';
import 'package:makolo_mobile/platform/permissions/permission_gateway.dart';

class FakePermissions implements PermissionGateway {
  FakePermissions(this.cameraDecision, {this.microphoneDecision});

  final PermissionDecision cameraDecision;
  final PermissionDecision? microphoneDecision;

  @override
  Future<bool> openSettings() async => true;

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async =>
      status(permission);

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async {
    if (permission == MakoloPermission.microphone) {
      return microphoneDecision ?? cameraDecision;
    }
    return cameraDecision;
  }
}

class FakeCameraSession implements IntegratedCameraSession {
  bool disposed = false;

  @override
  Future<IntegratedCapture> capturePhoto() async =>
      const IntegratedCapture(path: '/tmp/photo.jpg', isVideo: false);

  @override
  Future<void> dispose() async => disposed = true;

  @override
  Widget preview() => const SizedBox.shrink();

  @override
  Future<void> startVideo() async {}

  @override
  Future<IntegratedCapture> stopVideo() async =>
      const IntegratedCapture(path: '/tmp/video.mp4', isVideo: true);
}

class FakeCamera implements IntegratedCamera {
  int opens = 0;
  final session = FakeCameraSession();

  @override
  Future<IntegratedCameraSession> open({
    MakoloCameraLens preferredLens = MakoloCameraLens.back,
    bool enableAudio = true,
  }) async {
    opens += 1;
    return session;
  }
}

void main() {
  test('camera denial prevents native camera opening', () async {
    final camera = FakeCamera();
    final result = await CameraCapability(
      permissions: FakePermissions(PermissionDecision.permanentlyDenied),
      camera: camera,
    ).open();

    expect(result.status, CameraCapabilityStatus.cameraSettingsRequired);
    expect(camera.opens, 0);
  });

  test('video audio requires microphone permission independently', () async {
    final camera = FakeCamera();
    final result = await CameraCapability(
      permissions: FakePermissions(
        PermissionDecision.granted,
        microphoneDecision: PermissionDecision.denied,
      ),
      camera: camera,
    ).open(enableAudio: true);

    expect(result.status, CameraCapabilityStatus.microphoneDenied);
    expect(camera.opens, 0);
  });

  test('granted camera capability returns a disposable native session', () async {
    final camera = FakeCamera();
    final result = await CameraCapability(
      permissions: FakePermissions(PermissionDecision.granted),
      camera: camera,
    ).open();

    expect(result.ready, isTrue);
    expect(camera.opens, 1);
    await result.session!.dispose();
    expect(camera.session.disposed, isTrue);
  });
}
