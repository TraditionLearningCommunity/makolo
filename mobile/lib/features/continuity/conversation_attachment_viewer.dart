import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:open_filex/open_filex.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:video_player/video_player.dart';

import '../../platform/media/private_media_views.dart';
import 'conversation_repository.dart';

/// Private download and ephemeral viewer. No bearer is exposed to external
/// renderers and no private attachment is registered as a durable Resource.
class ConversationAttachmentViewer extends StatefulWidget {
  const ConversationAttachmentViewer({
    super.key,
    required this.repository,
    required this.attachment,
    this.inline = false,
  });

  final ConversationRepository repository;
  final Map<String, dynamic> attachment;
  final bool inline;

  @override
  State<ConversationAttachmentViewer> createState() =>
      _ConversationAttachmentViewerState();
}

class _ConversationAttachmentViewerState
    extends State<ConversationAttachmentViewer> {
  late Future<File> _future;
  File? _file;
  String? _error;
  AudioPlayer? _audio;
  VideoPlayerController? _video;

  @override
  void initState() {
    super.initState();
    _download();
  }

  void _download() {
    _future = widget.repository.downloadAttachment(
      attachmentId: widget.attachment['id']?.toString() ?? '',
      filename: widget.attachment['name']?.toString() ?? 'fichier',
    ).then((file) async {
      _file = file;
      final kind = widget.attachment['kind']?.toString();
      if (kind == 'audio' || kind == 'voice') {
        final player = AudioPlayer();
        try {
          await player.setFilePath(file.path);
          _audio = player;
        } on Object {
          await player.dispose();
          _error = 'Lecture audio indisponible.';
        }
      } else if (kind == 'video') {
        final player = await const PrivateVideoControllerFactory().open(file.path);
        try {
          await player.initialize();
          _video = player;
        } on Object {
          await player.dispose();
          _error = 'Lecture vidéo indisponible.';
        }
      }
      return file;
    });
  }

  void _retry() => setState(() {
    _error = null;
    _download();
  });

  @override
  void dispose() {
    final audio = _audio;
    final video = _video;
    if (audio != null) unawaited(audio.dispose());
    if (video != null) unawaited(video.dispose());
    final file = _file;
    if (file != null) {
      unawaited(file.delete().catchError((Object _) => file));
    }
    super.dispose();
  }

  Widget _read(File file) {
    final kind = widget.attachment['kind']?.toString() ?? 'file';
    final mime = widget.attachment['mime_type']?.toString() ?? '';
    if (kind == 'image') {
      return InteractiveViewer(
        minScale: 1, maxScale: 5,
        child: Center(child: Image.file(file, fit: BoxFit.contain)),
      );
    }
    if (mime == 'application/pdf') {
      return PrivatePdfView(path: file.path);
    }
    if (kind == 'audio' || kind == 'voice') {
      final player = _audio;
      if (player == null) return Text(_error ?? 'Lecture indisponible.');
      return Center(
        child: StreamBuilder<bool>(
          stream: player.playingStream,
          builder: (context, state) {
            final playing = state.data == true;
            return FilledButton.icon(
              onPressed: () async {
                if (playing) {
                  await player.pause();
                } else {
                  await player.seek(Duration.zero);
                  unawaited(player.play());
                }
              },
              icon: Icon(playing
                  ? Icons.pause_rounded : Icons.play_arrow_rounded),
              label: Text(playing ? 'Pause' : 'Écouter'),
            );
          },
        ),
      );
    }
    if (kind == 'video') {
      final player = _video;
      if (player == null) return Text(_error ?? 'Vidéo indisponible.');
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AspectRatio(
              aspectRatio: player.value.aspectRatio,
              child: VideoPlayer(player),
            ),
            FilledButton.icon(
              onPressed: () => setState(() {
                if (player.value.isPlaying) {
                  player.pause();
                } else {
                  player.play();
                }
              }),
              icon: Icon(player.value.isPlaying
                  ? Icons.pause_rounded : Icons.play_arrow_rounded),
              label: Text(player.value.isPlaying ? 'Pause' : 'Lire'),
            ),
          ],
        ),
      );
    }
    if (mime == 'text/plain') {
      return FutureBuilder<String>(
        future: file.readAsString(),
        builder: (context, snapshot) {
          if (snapshot.hasError) return const Text('Texte indisponible.');
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          return SingleChildScrollView(
            padding: const EdgeInsets.all(18),
            child: SelectableText(snapshot.data!),
          );
        },
      );
    }
    // DOC/DOCX are offered only to installed native viewers after explicit
    // action. There is no public URL or silent permanent export.
    return Center(
      child: FilledButton.icon(
        onPressed: () async {
          final result = await OpenFilex.open(file.path);
          if (result.type != ResultType.done && mounted) {
            setState(() => _error = 'Aucune application ne peut ouvrir ce document.');
          }
        },
        icon: const Icon(Icons.open_in_new_rounded),
        label: const Text('Ouvrir ce document'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.inline) {
      final kind = widget.attachment['kind']?.toString() ?? 'file';
      final mime = widget.attachment['mime_type']?.toString() ?? '';
      final height = kind == 'image' || kind == 'video' ||
              mime == 'application/pdf' || mime == 'text/plain'
          ? 220.0 : 92.0;
      return SizedBox(
        height: height,
        width: double.infinity,
        child: FutureBuilder<File>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return const Center(child: Icon(Icons.broken_image_outlined));
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            if (kind != 'image' && kind != 'video' &&
                kind != 'audio' && kind != 'voice' &&
                mime != 'application/pdf' && mime != 'text/plain') {
              return const Center(child: Icon(Icons.description_outlined, size: 42));
            }
            return ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: _read(snapshot.data!),
            );
          },
        ),
      );
    }
    final title = widget.attachment['name']?.toString() ?? 'Pièce jointe';
    return SafeArea(
      child: Scaffold(
        appBar: AppBar(
          title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
          actions: [
            IconButton(
              tooltip: 'Fermer',
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.close_rounded),
            ),
          ],
        ),
        body: FutureBuilder<File>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('Pièce inaccessible ou connexion indisponible.'),
                    TextButton(onPressed: _retry, child: const Text('Réessayer')),
                  ],
                ),
              );
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            return Column(
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(_error!, style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    )),
                  ),
                Expanded(child: _read(snapshot.data!)),
              ],
            );
          },
        ),
      ),
    );
  }
}
