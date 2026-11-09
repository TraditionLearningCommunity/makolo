import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:open_filex/open_filex.dart';
import 'package:video_player/video_player.dart';

import '../../platform/media/private_media_views.dart';
import '../../platform/downloads/device_downloads.dart';
import '../../platform/sharing/share_gateway.dart';
import 'conversation_repository.dart';

typedef PrivateMediaDownloader = Future<File> Function({
  required String attachmentId,
  required String filename,
});

/// Private download and ephemeral viewer. No bearer is exposed to external
/// renderers and no private attachment is registered as a durable Resource.
class ConversationAttachmentViewer extends StatefulWidget {
  const ConversationAttachmentViewer({
    super.key,
    this.repository,
    this.download,
    required this.attachment,
    this.inline = false,
    this.gallery = const [],
    this.initialIndex = 0,
    this.downloads = const AndroidDeviceDownloads(),
    this.sharing = const SystemShareGateway(),
  });

  final ConversationRepository? repository;
  final PrivateMediaDownloader? download;
  final Map<String, dynamic> attachment;
  final bool inline;
  final List<Map<String, dynamic>> gallery;
  final int initialIndex;
  final DeviceDownloads downloads;
  final ShareGateway sharing;

  @override
  State<ConversationAttachmentViewer> createState() =>
      _ConversationAttachmentViewerState();
}

class _ConversationAttachmentViewerState
    extends State<ConversationAttachmentViewer> {
  Future<File>? _future;
  late int _index;
  int _generation = 0;
  bool _exporting = false;
  Map<String, dynamic> get _attachment => widget.gallery.isEmpty
      ? widget.attachment : widget.gallery[_index];
  File? _file;
  String? _error;
  AudioPlayer? _audio;
  VideoPlayerController? _video;

  @override
  void initState() {
    super.initState();
    _index = widget.gallery.isEmpty
        ? 0 : widget.initialIndex.clamp(0, widget.gallery.length - 1).toInt();
    if (!widget.inline || _attachment['kind'] == 'image') _download();
  }

  void _download({bool playAudio = false}) {
    final current = _attachment;
    final generation = ++_generation;
    final downloader = widget.download ?? widget.repository?.downloadAttachment;
    if (downloader == null) {
      _error = 'Lecteur privé indisponible.';
      return;
    }
    _future = downloader(
          attachmentId: current['id']?.toString() ?? '',
          filename: current['name']?.toString() ?? 'fichier',
        )
        .then((file) async {
          if (!mounted || generation != _generation) {
            await file.delete().catchError((Object _) => file);
            throw StateError('Média abandonné.');
          }
          _file = file;
          final kind = current['kind']?.toString();
          if (kind == 'audio' || kind == 'voice') {
            final player = AudioPlayer();
            try {
              await player.setFilePath(file.path);
              if (mounted && generation == _generation) {
                _audio = player;
                if (playAudio) unawaited(player.play());
              } else {
                await player.dispose();
              }
            } on Object {
              await player.dispose();
              _error = 'Lecture audio indisponible.';
            }
          } else if (kind == 'video') {
            final player = await const PrivateVideoControllerFactory().open(
              file.path,
            );
            try {
              await player.initialize();
              if (mounted && generation == _generation) {
                _video = player;
              } else {
                await player.dispose();
              }
            } on Object {
              await player.dispose();
              _error = 'Lecture vidéo indisponible.';
            }
          }
          if (!mounted || generation != _generation) {
            throw StateError('Média abandonné.');
          }
          setState(() {});
          return file;
        });
  }

  void _retry() => setState(() {
    _error = null;
    _download();
  });

  Future<void> _release() async {
    final audio = _audio;
    final video = _video;
    final file = _file;
    _audio = null;
    _video = null;
    _file = null;
    if (audio != null) await audio.dispose();
    if (video != null) await video.dispose();
    if (file != null) {
      await file.delete().catchError((Object _) => file);
    }
  }

  Future<void> _navigate(int next) async {
    if (widget.gallery.isEmpty || next < 0 ||
        next >= widget.gallery.length || _exporting) return;
    ++_generation;
    await _release();
    if (!mounted) return;
    setState(() {
      _index = next;
      _error = null;
      _download();
    });
  }

  Future<void> _fileAction({required bool share}) async {
    final file = _file;
    if (file == null || _exporting) return;
    setState(() => _exporting = true);
    try {
      if (share) {
        await widget.sharing.shareFiles(paths: [file.path]);
      } else {
        final name = _attachment['name']?.toString() ?? 'Document Makolo';
        final dot = name.lastIndexOf('.');
        final stem = dot > 0 ? name.substring(0, dot) : name;
        final extension = dot > 0 ? name.substring(dot + 1) : 'bin';
        final saved = await widget.downloads.save(
          source: file,
          fileName: makoloDownloadName(stem, extension),
          mimeType: _attachment['mime_type']?.toString() ??
              'application/octet-stream',
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Enregistré : ' + saved)),
          );
        }
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(share
              ? 'Partage indisponible.' : 'Téléchargement indisponible.')),
        );
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  void dispose() {
    ++_generation;
    unawaited(_release());
    super.dispose();
  }

  String _time(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = (duration.inSeconds % 60).toString().padLeft(2, '0');
    return minutes.toString() + ':' + seconds;
  }

  Widget _read(File file) {
    final kind = _attachment['kind']?.toString() ?? 'file';
    final mime = _attachment['mime_type']?.toString() ?? '';
    if (kind == 'image') {
      return InteractiveViewer(
        minScale: 1,
        maxScale: 5,
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
        child: StreamBuilder<Duration>(
          stream: player.positionStream,
          builder: (context, state) {
            final duration = player.duration ?? Duration.zero;
            final position = state.data ?? Duration.zero;
            final maximum = duration.inMilliseconds > 0
                ? duration.inMilliseconds.toDouble() : 1.0;
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                StreamBuilder<bool>(
                  stream: player.playingStream,
                  builder: (context, playingState) => IconButton.filled(
                    tooltip: playingState.data == true ? 'Pause' : 'Écouter',
                    onPressed: () async {
                      if (player.playing) {
                        await player.pause();
                      } else {
                        if (duration > Duration.zero && position >= duration) {
                          await player.seek(Duration.zero);
                        }
                        unawaited(player.play());
                      }
                    },
                    icon: Icon(player.playing
                        ? Icons.pause_rounded : Icons.play_arrow_rounded),
                  ),
                ),
                Slider(
                  value: position.inMilliseconds.toDouble().clamp(0, maximum).toDouble(),
                  max: maximum,
                  onChanged: duration > Duration.zero
                      ? (v) => player.seek(Duration(milliseconds: v.round()))
                      : null,
                ),
                Text(_time(position) + ' / ' + _time(duration)),
              ],
            );
          },
        ),
      );
    }
    if (kind == 'video') {
      final player = _video;
      if (player == null) return Text(_error ?? 'Vidéo indisponible.');
      return Center(
        child: AnimatedBuilder(
          animation: player,
          builder: (context, _) {
            final value = player.value;
            final maximum = value.duration.inMilliseconds > 0
                ? value.duration.inMilliseconds.toDouble() : 1.0;
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Flexible(
                  child: AspectRatio(
                    aspectRatio: value.aspectRatio > 0 ? value.aspectRatio : 1,
                    child: VideoPlayer(player),
                  ),
                ),
                Row(
                  children: [
                    IconButton(
                      tooltip: value.isPlaying ? 'Pause' : 'Lire',
                      onPressed: () {
                        if (value.isPlaying) {
                          player.pause();
                        } else {
                          if (value.position >= value.duration) {
                            player.seekTo(Duration.zero);
                          }
                          player.play();
                        }
                      },
                      icon: Icon(value.isPlaying
                          ? Icons.pause_rounded : Icons.play_arrow_rounded),
                    ),
                    Expanded(
                      child: Slider(
                        value: value.position.inMilliseconds
                            .toDouble().clamp(0, maximum).toDouble(),
                        max: maximum,
                        onChanged: (v) => player.seekTo(
                          Duration(milliseconds: v.round()),
                        ),
                      ),
                    ),
                    Text(_time(value.position) + '/' + _time(value.duration)),
                  ],
                ),
              ],
            );
          },
        ),
      );
    }
    if (mime == 'text/plain') {
      return FutureBuilder<String>(
        future: file.readAsString(),
        builder: (context, snapshot) {
          if (snapshot.hasError) return const Text('Texte indisponible.');
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
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
            setState(
              () => _error = 'Aucune application ne peut ouvrir ce document.',
            );
          }
        },
        icon: const Icon(Icons.open_in_new_rounded),
        label: const Text('Ouvrir ce document'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final kind = _attachment['kind']?.toString() ?? 'file';
    final mime = _attachment['mime_type']?.toString() ?? '';
    if (widget.inline) {
      final height = kind == 'image' || kind == 'video' ||
              mime == 'application/pdf' || mime == 'text/plain'
          ? 220.0 : kind == 'voice' || kind == 'audio' ? 144.0 : 84.0;
      if (_future == null) {
        final label = switch (kind) {
          'audio' || 'voice' => 'Écouter le message vocal',
          'video' => 'Lire la vidéo',
          _ when mime == 'application/pdf' => 'Lire le PDF',
          _ when mime == 'text/plain' => 'Lire le document',
          _ => 'Ouvrir le document',
        };
        final icon = switch (kind) {
          'audio' || 'voice' => Icons.play_circle_outline_rounded,
          'video' => Icons.ondemand_video_outlined,
          _ => Icons.description_outlined,
        };
        return SizedBox(
          height: kind == 'video' || mime == 'application/pdf' ? 96 : 72,
          child: Center(
            child: TextButton.icon(
              onPressed: () => setState(
                () => _download(playAudio: kind == 'audio' || kind == 'voice'),
              ),
              icon: Icon(icon),
              label: Text(label),
            ),
          ),
        );
      }
      return SizedBox(
        height: height,
        width: double.infinity,
        child: FutureBuilder<File>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(
                child: TextButton.icon(
                  onPressed: _retry,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Réessayer le média'),
                ),
              );
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            if (kind != 'image' && kind != 'video' &&
                kind != 'audio' && kind != 'voice' &&
                mime != 'application/pdf' && mime != 'text/plain') {
              return const Center(child: Icon(
                Icons.description_outlined, size: 42));
            }
            return ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: _read(snapshot.data!),
            );
          },
        ),
      );
    }

    final title = _attachment['name']?.toString() ?? 'Pièce jointe';
    final galleryLength = widget.gallery.length;
    return SafeArea(
      child: Scaffold(
        appBar: AppBar(
          title: Text(galleryLength > 1
              ? title + ' · ' + (_index + 1).toString() +
                  '/' + galleryLength.toString()
              : title, maxLines: 1, overflow: TextOverflow.ellipsis),
          actions: [
            if (galleryLength > 1) ...[
              IconButton(
                tooltip: 'Média précédent',
                onPressed: _index > 0 ? () => _navigate(_index - 1) : null,
                icon: const Icon(Icons.chevron_left_rounded),
              ),
              IconButton(
                tooltip: 'Média suivant',
                onPressed: _index + 1 < galleryLength
                    ? () => _navigate(_index + 1) : null,
                icon: const Icon(Icons.chevron_right_rounded),
              ),
            ],
            IconButton(
              tooltip: 'Télécharger',
              onPressed: _file == null || _exporting
                  ? null : () => _fileAction(share: false),
              icon: const Icon(Icons.download_outlined),
            ),
            IconButton(
              tooltip: 'Partager le fichier',
              onPressed: _file == null || _exporting
                  ? null : () => _fileAction(share: true),
              icon: const Icon(Icons.share_outlined),
            ),
            IconButton(
              tooltip: 'Fermer',
              onPressed: _exporting ? null : () => Navigator.of(context).pop(),
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
                if ((_attachment['caption']?.toString().trim() ?? '').isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      _attachment['caption'].toString().trim(),
                      style: Theme.of(context).textTheme.bodyMedium,
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(_error!, style: TextStyle(
                      color: Theme.of(context).colorScheme.error)),
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
