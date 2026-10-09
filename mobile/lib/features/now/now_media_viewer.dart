import 'dart:io';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../network/makolo_api_client.dart';
import '../../data/files/profile_paths.dart';
import '../../platform/media/private_media_views.dart';
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
  if (!uri.path.startsWith('/api/v1/') ||
      uri.path.contains('//') ||
      uri.path.endsWith('/../')) {
    return null;
  }
  return uri.toString().substring(1);
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
    this.temporaryDirectory,
    this.profileId,
  });

  final NowMediaBindingPresentation media;
  final MakoloApiClient api;
  final ShareGateway sharing;
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
      if (mounted)
        setState(() {
          _loading = false;
          _error = 'Ce média ne dispose pas d’un accès autorisé.';
        });
      return;
    }
    File? file;
    try {
      final profile = widget.profileId;
      if (widget.temporaryDirectory == null && profile == null) {
        throw StateError('Authenticated profile required for private media.');
      }
      final temporary = widget.temporaryDirectory ??
          await ProfilePaths.reconstructibleCache(profile!);
      final dir = Directory('${temporary.path}/makolo-now-media');
      await dir.create(recursive: true);
      file = File(
        '${dir.path}/now-${DateTime.now().microsecondsSinceEpoch}.${nowMediaExtension(widget.media)}',
      );
      await widget.api.download(
        path,
        destinationPath: file.path,
        cancel: _cancel,
      );
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
      if (mounted)
        setState(() {
          _error = 'Impossible de charger ce média. Vérifiez votre connexion et vos droits.';
          _loading = false;
        });
    }
  }

  Future<void> _save() async {
    final file = _file;
    if (file == null || _sharing) return;
    setState(() => _sharing = true);
    try {
      // Native share sheet allows the person to choose Save to Files or
      // another destination; Makolo never silently exports private media.
      await widget.sharing.shareFiles(paths: [file.path]);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Impossible de proposer l’enregistrement.'),
          ),
        );
      }
    } finally {
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
              tooltip: 'Enregistrer sur l’appareil',
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
