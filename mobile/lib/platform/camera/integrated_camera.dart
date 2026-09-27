import 'package:camera/camera.dart';
import 'package:flutter/widgets.dart';

enum MakoloCameraLens { front, back, external }

class IntegratedCapture {
  const IntegratedCapture({
    required this.path,
    required this.isVideo,
  });

  final String path;
  final bool isVideo;
}

abstract interface class IntegratedCameraSession {
  Widget preview();
  Future<IntegratedCapture> capturePhoto();
  Future<void> startVideo();
  Future<IntegratedCapture> stopVideo();
  Future<void> dispose();
}

abstract interface class IntegratedCamera {
  Future<IntegratedCameraSession> open({
    MakoloCameraLens preferredLens = MakoloCameraLens.back,
    bool enableAudio = true,
  });
}

class FlutterIntegratedCamera implements IntegratedCamera {
  const FlutterIntegratedCamera();

  @override
  Future<IntegratedCameraSession> open({
    MakoloCameraLens preferredLens = MakoloCameraLens.back,
    bool enableAudio = true,
  }) async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      throw StateError('No integrated camera is available.');
    }
    final desired = switch (preferredLens) {
      MakoloCameraLens.front => CameraLensDirection.front,
      MakoloCameraLens.back => CameraLensDirection.back,
      MakoloCameraLens.external => CameraLensDirection.external,
    };
    final description = cameras.firstWhere(
      (camera) => camera.lensDirection == desired,
      orElse: () => cameras.first,
    );
    final controller = CameraController(
      description,
      ResolutionPreset.high,
      enableAudio: enableAudio,
    );
    await controller.initialize();
    return _FlutterIntegratedCameraSession(controller);
  }
}

class _FlutterIntegratedCameraSession implements IntegratedCameraSession {
  _FlutterIntegratedCameraSession(this._controller);

  final CameraController _controller;

  @override
  Widget preview() => CameraPreview(_controller);

  @override
  Future<IntegratedCapture> capturePhoto() async {
    final file = await _controller.takePicture();
    return IntegratedCapture(path: file.path, isVideo: false);
  }

  @override
  Future<void> startVideo() => _controller.startVideoRecording();

  @override
  Future<IntegratedCapture> stopVideo() async {
    final file = await _controller.stopVideoRecording();
    return IntegratedCapture(path: file.path, isVideo: true);
  }

  @override
  Future<void> dispose() async {
    await _controller.dispose();
  }
}
