import 'dart:io';

import 'package:flutter/material.dart';

import '../../platform/media/private_media_views.dart';
import 'resource_repository.dart';

class ResourceFileViewer extends StatefulWidget {
  const ResourceFileViewer({
    super.key,
    required this.repository,
    required this.assetId,
    required this.title,
    required this.versionNumber,
    required this.mimeType,
    required this.downloadPath,
  });

  final ResourceRepository repository;
  final String assetId;
  final String title;
  final int versionNumber;
  final String? mimeType;
  final String downloadPath;

  @override
  State<ResourceFileViewer> createState() => _ResourceFileViewerState();
}

class _ResourceFileViewerState extends State<ResourceFileViewer> {
  String? _path;
  String? _error;
  bool _loading = true;
  double? _progress;

  bool get _textPreview =>
      widget.mimeType ==
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
      widget.mimeType == 'text/plain';

  bool get _supported =>
      _textPreview ||
      widget.mimeType == 'application/pdf' ||
      widget.mimeType == 'image/jpeg' ||
      widget.mimeType == 'image/png' ||
      widget.mimeType == 'image/webp' ||
      widget.mimeType == 'image/gif';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!_supported) {
      setState(() {
        _loading = false;
        _error = 'Ce type de fichier n’est pas encore lisible dans Makolo.';
      });
      return;
    }
    try {
      final path = await widget.repository.downloadVersionForReader(
        path: widget.downloadPath,
        assetId: widget.assetId,
        title: widget.title,
        versionNumber: widget.versionNumber,
        extension: _readerExtension(widget.mimeType),
        textPreview: _textPreview,
        onProgress: (transferred, total) {
          if (!mounted || total <= 0) return;
          setState(() => _progress = transferred / total);
        },
      );
      if (!mounted) {
        await _discard(path);
        return;
      }
      setState(() {
        _path = path;
        _loading = false;
        _progress = null;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _loading = false;
          _progress = null;
          _error = 'Impossible d’ouvrir ce fichier.';
        });
      }
    }
  }

  @override
  void dispose() {
    final path = _path;
    if (path != null) {
      _discard(path);
    }
    super.dispose();
  }

  Future<void> _discard(String path) async {
    final file = File(path);
    try {
      if (await file.exists()) await file.delete();
      final parent = file.parent;
      if (await parent.exists()) await parent.delete(recursive: true);
    } on FileSystemException {
      // Reader bytes are transient and cleanup is best-effort.
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: SafeArea(
      child: _loading
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator.adaptive(),
                    if (_progress != null) ...[
                      const SizedBox(height: 16),
                      LinearProgressIndicator(value: _progress),
                    ],
                  ],
                ),
              ),
            )
          : _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(_error!, textAlign: TextAlign.center),
              ),
            )
          : _content(),
    ),
  );

  Widget _content() {
    final path = _path;
    if (path == null) {
      return const Center(child: Text('Fichier indisponible.'));
    }
    if (_textPreview) {
      return FutureBuilder<String>(
        future: File(path).readAsString(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return const Center(child: Text('Document illisible.'));
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator.adaptive());
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: SelectableText(snapshot.data!),
          );
        },
      );
    }
    if (widget.mimeType == 'application/pdf') {
      return PrivatePdfView(path: path);
    }
    return InteractiveViewer(
      minScale: 0.5,
      maxScale: 5,
      child: Center(
        child: Image.file(
          File(path),
          errorBuilder: (context, error, stackTrace) =>
              const Text('Image illisible.'),
        ),
      ),
    );
  }
}

String _readerExtension(String? mimeType) => switch (mimeType) {
  'application/pdf' => 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document' =>
    'txt',
  'text/plain' => 'txt',
  'image/jpeg' => 'jpg',
  'image/png' => 'png',
  'image/webp' => 'webp',
  'image/gif' => 'gif',
  _ => 'bin',
};
