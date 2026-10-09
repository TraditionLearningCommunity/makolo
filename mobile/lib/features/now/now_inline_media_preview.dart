import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../data/files/profile_paths.dart';
import '../../network/makolo_api_client.dart';
import '../../presentation/contracts/now_presentation.dart';
import 'now_media_viewer.dart';

/// A private inline photo in Now. It never requests an unauthenticated URL,
/// and its transient bytes and decoded image are evicted when unmounted.
/// Videos/documents keep a calm poster and open the in-app viewer on demand.
class NowInlineMediaPreview extends StatefulWidget {
  const NowInlineMediaPreview({
    super.key,
    required this.media,
    required this.api,
    required this.profileId,
    required this.placeholder,
    this.temporaryDirectory,
  });

  final NowMediaBindingPresentation media;
  final MakoloApiClient api;
  final String profileId;
  final Widget placeholder;
  final Directory? temporaryDirectory;

  @override
  State<NowInlineMediaPreview> createState() => _NowInlineMediaPreviewState();
}

class _NowInlineMediaPreviewState extends State<NowInlineMediaPreview> {
  File? _downloaded;
  MakoloCancelHandle? _cancel;
  bool _loading = false;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _prepare();
  }

  @override
  void didUpdateWidget(covariant NowInlineMediaPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.media.resourceRef != widget.media.resourceRef ||
        oldWidget.media.url != widget.media.url ||
        oldWidget.media.authorized != widget.media.authorized ||
        oldWidget.profileId != widget.profileId) {
      _cancel?.cancel();
      unawaited(_discard(_downloaded));
      _downloaded = null;
      _loading = false;
      _failed = false;
      _prepare();
    }
  }

  Future<void> _prepare() async {
    if (widget.media.kind != NowMediaKind.image) return;
    final path = nowAuthorizedMediaPath(widget.media);
    if (path == null || widget.profileId.isEmpty) return;
    final cancel = MakoloCancelHandle();
    _cancel = cancel;
    if (mounted) {
      setState(() {
        _loading = true;
        _failed = false;
      });
    }

    File? downloaded;
    try {
      final base = widget.temporaryDirectory ??
          await ProfilePaths.reconstructibleCache(widget.profileId);
      final directory = Directory('${base.path}/now-previews');
      await directory.create(recursive: true);
      downloaded = File(
        '${directory.path}/preview-${DateTime.now().microsecondsSinceEpoch}.'
        '${nowMediaExtension(widget.media)}',
      );
      await widget.api.download(
        path,
        destinationPath: downloaded.path,
        cancel: cancel,
      );
      if (!mounted || cancel.isCancelled || _cancel != cancel) {
        unawaited(_discard(downloaded));
        return;
      }
      setState(() {
        _downloaded = downloaded;
        _loading = false;
      });
    } on Object {
      unawaited(_discard(downloaded));
      if (mounted && _cancel == cancel) {
        setState(() {
          _loading = false;
          _failed = true;
        });
      }
    }
  }

  Future<void> _discard(File? file) async {
    if (file == null) return;
    try {
      await FileImage(file).evict();
      if (await file.exists()) await file.delete();
    } on FileSystemException {
      // Cache cleanup must not interrupt navigation.
    }
  }

  @override
  void dispose() {
    _cancel?.cancel();
    unawaited(_discard(_downloaded));
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final file = _downloaded;
    if (file == null) {
      return Stack(
        fit: StackFit.expand,
        children: [
          widget.placeholder,
          if (_loading)
            const Align(
              alignment: Alignment.bottomCenter,
              child: LinearProgressIndicator(minHeight: 2),
            ),
          if (_failed)
            const Align(
              alignment: Alignment.bottomRight,
              child: Padding(
                padding: EdgeInsets.all(8),
                child: Icon(Icons.cloud_off_outlined),
              ),
            ),
        ],
      );
    }
    return Image.file(
      file,
      fit: BoxFit.cover,
      errorBuilder: (context, error, stackTrace) => widget.placeholder,
    );
  }
}
