import 'dart:io';

import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../platform/media/private_media_views.dart';

class PreparationLocalFileArgs {
  const PreparationLocalFileArgs({
    required this.path,
    required this.title,
    this.mimeType,
  });

  final String path;
  final String title;
  final String? mimeType;
}

class PreparationLocalFileScreen extends StatelessWidget {
  const PreparationLocalFileScreen({super.key, required this.args});

  final PreparationLocalFileArgs args;

  @override
  Widget build(BuildContext context) {
    final mime = (args.mimeType ?? '').toLowerCase();
    return Scaffold(
      appBar: AppBar(title: Text(args.title)),
      body: SafeArea(
        child: switch (mime) {
          'application/pdf' => PrivatePdfView(path: args.path),
          'image/jpeg' || 'image/png' || 'image/webp' => InteractiveViewer(
            minScale: 0.8,
            maxScale: 4,
            child: Center(
              child: Image.file(
                File(args.path),
                fit: BoxFit.contain,
                semanticLabel: args.title,
              ),
            ),
          ),
          _ => Padding(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            child: Center(
              child: Text(
                'Ce document est téléchargé sur cet appareil. '
                'Aucun aperçu intégré sûr n’est disponible pour ce format.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        },
      ),
    );
  }
}
