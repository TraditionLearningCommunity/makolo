import 'dart:io';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../network/makolo_api_client.dart';
import '../../data/files/profile_paths.dart';
import '../../data/files/profile_recognition_image_store.dart';
import '../../platform/media/private_media_views.dart';
import '../../platform/downloads/device_downloads.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../presentation/contracts/now_presentation.dart';

/// Only first-party authenticated API paths may be downloaded from Now.
/// Neither a media reference nor a presentation authorization flag is a URL.
String? nowAuthorizedMediaPath(NowMediaBindingPresentation binding) {
  if (!binding.canRender) return null;
  final raw = binding.url;
  if (raw == null || raw.trim().isEmpty) return null;
  final uri = Uri.tryParse(raw);
  if (uri == null ||
      uri.hasScheme ||
      uri.hasAuthority ||
      raw.startsWith('//') ||
      uri.pathSegments.any((part) => part == '..' || part == '.')) {
    return null;
  }
  final permitted = RegExp(
    r'^/api/v1/me/now/media/journey-artifacts/'
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/$',
  );
  final publicUseId = binding.resourceRef.startsWith('presentation_media_use:')
      ? binding.resourceRef.substring('presentation_media_use:'.length)
      : null;
  final published = RegExp(
    r'^/presentation/media/uses/'
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/file/$',
  );
  final publicRecognition =
      publicUseId != null &&
      uri.path == '/presentation/media/uses/$publicUseId/file/' &&
      binding.kind == NowMediaKind.image &&
      binding.purpose == NowMediaPurpose.recognize &&
      published.hasMatch(uri.path) &&
      !uri.hasQuery &&
      !uri.hasFragment;
  final privateArtifact =
      binding.resourceRef.startsWith('journey_artifact:') &&
      permitted.hasMatch(uri.path) &&
      !uri.hasFragment &&
      (binding.kind == NowMediaKind.document
          ? uri.query == 'view=text'
          : !uri.hasQuery);
  if (!publicRecognition && !privateArtifact) return null;
  return uri.toString().substring(1);
}

/// A separate owner-issued route allows saving the original DOCX instead of
/// exporting the plain-text reading projection. No arbitrary URL is trusted.
String? nowAuthorizedOriginalDownloadPath(NowMediaBindingPresentation binding) {
  final preview = nowAuthorizedMediaPath(binding);
  final original = binding.downloadUrl;
  if (preview == null || original == null || !original.startsWith('/')) {
    return null;
  }
  final uri = Uri.tryParse(original);
  if (uri == null || uri.hasScheme || uri.hasAuthority || uri.hasQuery) {
    return null;
  }
  final source = binding.url?.split('?').first;
  if (source != original) return null;
  return original.substring(1);
}

String nowOriginalDocumentExtension(NowMediaBindingPresentation media) {
  return media.mimeType == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ? 'docx'
      : 'txt';
}

String nowMediaExtension(NowMediaBindingPresentation media) {
  return switch (media.kind) {
    NowMediaKind.image => switch (media.mimeType) {
      'image/png' => 'png',
      'image/webp' => 'webp',
      'image/gif' => 'gif',
      _ => 'jpg',
    },
    NowMediaKind.pdf => 'pdf',
    NowMediaKind.document => 'txt',
    NowMediaKind.video => 'mp4',
    NowMediaKind.audio => 'mp3',
    _ => 'bin',
  };
}

/// A transient authenticated reader. No media is saved to the user's
/// documents or exposed through an external player without an explicit tap.
class NowMediaViewer extends StatefulWidget {
  const NowMediaViewer({
    super.key,
    required this.media,
    required this.api,
    this.sharing = const SystemShareGateway(),
    this.downloads = const AndroidDeviceDownloads(),
    this.temporaryDirectory,
    this.profileId,
  });

  final NowMediaBindingPresentation media;
  final MakoloApiClient api;
  final ShareGateway sharing;
  final DeviceDownloads downloads;
  final Directory? temporaryDirectory;
  final String? profileId;

  @override
  State<NowMediaViewer> createState() => _NowMediaViewerState();
}

class _NowMediaViewerState extends State<NowMediaViewer> {
  File? _file;
  VideoPlayerController? _player;
  String? _error;
  bool _loading = true;
  bool _sharing = false;
  final MakoloCancelHandle _cancel = MakoloCancelHandle();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final path = nowAuthorizedMediaPath(widget.media);
    if (path == null) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Ce média ne dispose pas d’un accès autorisé.';
        });
      }
      return;
    }
    File? file;
    try {
      final profile = widget.profileId;
      if (widget.temporaryDirectory == null && profile == null) {
        throw StateError('Authenticated profile required for private media.');
      }
      final Directory temporary;
      if (widget.temporaryDirectory != null) {
        temporary = widget.temporaryDirectory!;
      } else {
        temporary = await ProfilePaths.reconstructibleCache(profile!);
      }
      final dir = Directory('${temporary.path}/makolo-now-media');
      if (!dir.existsSync()) await dir.create(recursive: true);
      file = File(
        '${dir.path}/now-${DateTime.now().microsecondsSinceEpoch}.${nowMediaExtension(widget.media)}',
      );
      // Published recognition photos already seen in Now remain readable
      // without a server. Private Journey files never enter this store.
      final published = widget.media.kind == NowMediaKind.image &&
          widget.media.purpose == NowMediaPurpose.recognize &&
          widget.media.resourceRef.startsWith('presentation_media_use:') &&
          profile != null;
      final recognition = published
          ? ProfileRecognitionImageStore(profileId: profile!)
          : null;
      final mediaKey = '/$path';
      final local = await recognition?.read(mediaKey);
      if (local != null) {
        await file.writeAsBytes(local, flush: true);
      } else {
        await widget.api.download(
          path,
          destinationPath: file.path,
          cancel: _cancel,
        );
        if (recognition != null && await file.length() <=
            ProfileRecognitionImageStore.maxImageBytes) {
          try {
            await recognition.save(mediaKey, await file.readAsBytes());
          } on Object {
            // Filesystem quota failures never suppress an acquired photo.
          }
        }
      }
      if (!mounted) {
        await file.delete();
        return;
      }
      VideoPlayerController? controller;
      if (widget.media.kind == NowMediaKind.video ||
          widget.media.kind == NowMediaKind.audio) {
        controller = await const PrivateVideoControllerFactory().open(
          file.path,
        );
      }
      if (!mounted) {
        await controller?.dispose();
        await file.delete();
        return;
      }
      setState(() {
        _file = file;
        _player = controller;
        _loading = false;
      });
    } on Object {
      if (file != null && await file.exists()) await file.delete();
      if (mounted) {
        setState(() {
          _error = 'Impossible de charger ce média. Vérifiez votre connexion et vos droits.';
          _loading = false;
        });
      }
    }
  }

  Future<void> _save() async {
    final file = _file;
    if (file == null || _sharing) return;
    setState(() => _sharing = true);
    File? original;
    try {
      // For text-rendered documents, allow the person to export the original
      // bytes, not only the safe plain-text projection used for reading.
      final originalPath = widget.media.kind == NowMediaKind.document
          ? nowAuthorizedOriginalDownloadPath(widget.media)
          : null;
      if (originalPath != null) {
        original = File(
          '${file.parent.path}/original-${DateTime.now().microsecondsSinceEpoch}.'
          '${nowOriginalDocumentExtension(widget.media)}',
        );
        await widget.api.download(
          originalPath,
          destinationPath: original.path,
          cancel: _cancel,
        );
      }
      // Only an explicit download tap exports the authorized bytes.
      final source = original ?? file;
      final extension = original != null
          ? nowOriginalDocumentExtension(widget.media)
          : nowMediaExtension(widget.media);
      final mime = original != null
          ? (widget.media.mimeType ?? 'application/octet-stream')
          : widget.media.kind == NowMediaKind.document
          ? 'text/plain'
          : (widget.media.mimeType ?? 'application/octet-stream');
      final name = await widget.downloads.save(
        source: source,
        fileName: makoloDownloadName(widget.media.label ?? 'Média Makolo', extension),
        mimeType: mime,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Enregistré dans Téléchargements : $name')),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Téléchargement impossible. Vérifiez les droits et l’appareil.'),
          ),
        );
      }
    } finally {
      if (original != null) {
        try {
          if (await original.exists()) await original.delete();
        } on FileSystemException {
          // The original copy is transient even if the share sheet fails.
        }
      }
      if (mounted) setState(() => _sharing = false);
    }
  }

  @override
  void dispose() {
    _cancel.cancel();
    final player = _player;
    if (player != null) {
      player.dispose().whenComplete(_deleteFile);
    } else {
      _deleteFile();
    }
    super.dispose();
  }

  Future<void> _deleteFile() async {
    final file = _file;
    if (file != null && await file.exists()) {
      try {
        await file.delete();
      } on FileSystemException {
        /* Temporary cleanup. */
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final media = widget.media;
    return Scaffold(
      appBar: AppBar(
        title: Text(media.label ?? 'Média'),
        actions: [
          if (_file != null)
            IconButton(
              tooltip: 'Télécharger dans Téléchargements',
              icon: const Icon(Icons.download_outlined),
              onPressed: _sharing ? null : _save,
            ),
        ],
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
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
  }

  Widget _content() {
    final file = _file;
    if (file == null) return const Center(child: Text('Média indisponible.'));
    return switch (widget.media.kind) {
      NowMediaKind.image => InteractiveViewer(
        minScale: 0.5,
        maxScale: 5,
        child: Center(
          child: Image.file(
            file,
            errorBuilder: (context, error, stack) =>
                const Text('Image illisible.'),
          ),
        ),
      ),
      NowMediaKind.pdf => PrivatePdfView(path: file.path),
      NowMediaKind.document => FutureBuilder<String>(
        future: file.readAsString(),
        builder: (context, snapshot) => snapshot.hasError
            ? const Center(child: Text('Document illisible.'))
            : snapshot.hasData
            ? SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: SelectableText(snapshot.data!),
              )
            : const Center(child: CircularProgressIndicator()),
      ),
      NowMediaKind.video || NowMediaKind.audio => _videoOrAudio(),
      _ => const Center(
        child: Text('Ce type de média n’est pas encore lisible ici.'),
      ),
    };
  }

  Widget _videoOrAudio() {
    final player = _player;
    if (player == null || !player.value.isInitialized) {
      return const Center(child: Text('Lecture indisponible.'));
    }
    final isAudio = widget.media.kind == NowMediaKind.audio;
    return Center(
      child: ValueListenableBuilder<VideoPlayerValue>(
        valueListenable: player,
        builder: (context, state, child) {
          final total = state.duration.inMilliseconds.toDouble();
          final current = state.position.inMilliseconds.toDouble();
          return Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (!isAudio)
                AspectRatio(
                  aspectRatio: state.aspectRatio > 0
                      ? state.aspectRatio
                      : 16 / 9,
                  child: VideoPlayer(player),
                )
              else
                const Icon(Icons.audiotrack_outlined, size: 80),
              const SizedBox(height: 16),
              Row(
                children: [
                  IconButton.filledTonal(
                    tooltip: state.isPlaying ? 'Pause' : 'Lire',
                    onPressed: () =>
                        state.isPlaying ? player.pause() : player.play(),
                    icon: Icon(
                      state.isPlaying ? Icons.pause : Icons.play_arrow,
                    ),
                  ),
                  Expanded(
                    child: Slider(
                      value: total > 0 ? current.clamp(0.0, total) : 0,
                      max: total > 0 ? total : 1,
                      onChanged: total > 0
                          ? (value) => player.seekTo(
                              Duration(milliseconds: value.toInt()),
                            )
                          : null,
                    ),
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}
