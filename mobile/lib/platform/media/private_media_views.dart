import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:video_player/video_player.dart';

class PrivatePdfView extends StatelessWidget {
  const PrivatePdfView({
    required this.path,
    super.key,
  });

  final String path;

  @override
  Widget build(BuildContext context) => PdfViewer.file(path);
}

class PrivateVideoControllerFactory {
  const PrivateVideoControllerFactory();

  Future<VideoPlayerController> open(String path) async {
    final controller = VideoPlayerController.file(File(path));
    await controller.initialize();
    return controller;
  }
}
