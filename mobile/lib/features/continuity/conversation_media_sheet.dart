import '../../platform/media/native_media_picker.dart';
import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import 'conversation_repository.dart';

String _newMediaReference() {
  final random = Random.secure();
  return 'mobile-media-${DateTime.now().microsecondsSinceEpoch}-'
      '${random.nextInt(0x7fffffff).toRadixString(16)}';
}

/// Opens on the actual capture or OS picker, never on an explanatory step.
class ConversationMediaSheet extends StatefulWidget {
  const ConversationMediaSheet({
    super.key,
    required this.mode,
    required this.repository,
    required this.conversationId,
    required this.capabilities,
    required this.onPublished,
    this.onQueued,
    this.representedSpaceId,
    this.lockedPointId,
    this.responsePointId,
  });

  final String mode; // voice, photo, camera, document
  final ConversationRepository repository;
  final String conversationId;
  final Map<String, dynamic> capabilities;
  final ValueChanged<String> onPublished;
  final VoidCallback? onQueued;
  final String? representedSpaceId;
  final String? lockedPointId;
  final String? responsePointId;

  @override
  State<ConversationMediaSheet> createState() => _ConversationMediaSheetState();
}

class _ConversationMediaSheetState extends State<ConversationMediaSheet> {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  final TextEditingController _caption = TextEditingController();
  Timer? _ticker;
  Duration _elapsed = Duration.zero;
  String _captureState = 'starting';
  String? _path;
  String? _filename;
  String? _kind;
  String? _ownedRecordPath;
  String? _reference;
  String? _error;
  String? _selectedAudienceId;
  String? _selectedPointId;
  bool _sending = false;
  bool _opening = false;
  // Capture state is owned here; no optimistic upload success.

  List<Map<String, dynamic>> _rows(String key) {
    final raw = widget.capabilities[key];
    if (raw is! List) return const [];
    return [
      for (final item in raw)
        if (item is Map)
          item.map((key, value) => MapEntry(key.toString(), value)),
    ];
  }

  bool get _requiresAudience =>
      widget.responsePointId == null &&
      widget.capabilities['text_mode'] == 'information' &&
      widget.capabilities['audience_selection_required'] == true;

  bool get _requiresPoint =>
      widget.responsePointId == null &&
      widget.lockedPointId == null &&
      widget.capabilities['text_mode'] == 'exchange_select';

  String? get _representedSpace =>
      widget.representedSpaceId != null &&
          widget.representedSpaceId ==
              widget.capabilities['representable_space_id']?.toString()
      ? widget.representedSpaceId
      : null;

  @override
  void initState() {
    super.initState();
    _selectedAudienceId = widget.capabilities['default_audience_id']
        ?.toString();
    _selectedPointId =
        widget.lockedPointId ??
        widget.capabilities['default_exchange_point_id']?.toString();
    _caption.addListener(_edited);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (widget.mode == 'voice') {
        unawaited(_startRecord());
      } else {
        unawaited(_pick());
      }
    });
  }

  void _edited() {
    _reference = null;
    if (_error != null && mounted) setState(() => _error = null);
  }

  Future<void> _startRecord() async {
    if (_opening || _sending) return;
    _opening = true;
    try {
      final allowed = await _recorder.hasPermission();
      if (!allowed) {
        if (mounted) {
          setState(() {
            _captureState = 'error';
            _error = 'Accès au micro refusé.';
          });
        }
        return;
      }
      final temp = await getTemporaryDirectory();
      final path =
          '${temp.path}/makolo-c4-${DateTime.now().microsecondsSinceEpoch}.m4a';
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 44100,
          numChannels: 1,
        ),
        path: path,
      );
      if (!mounted) {
        await _recorder.cancel();
        return;
      }
      _ticker?.cancel();
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted && _captureState == 'recording') {
          setState(() => _elapsed += const Duration(seconds: 1));
        }
      });
      setState(() {
        _captureState = 'recording';
        _ownedRecordPath = path;
        _reference = null;
        _elapsed = Duration.zero;
        _error = null;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _captureState = 'error';
          _error = 'Micro indisponible sur cet appareil.';
        });
      }
    } finally {
      _opening = false;
    }
  }

  Future<void> _pause() async {
    if (_captureState != 'recording') return;
    try {
      await _recorder.pause();
      if (mounted) setState(() => _captureState = 'paused');
    } on Object {
      if (mounted) setState(() => _error = 'Pause impossible.');
    }
  }

  Future<void> _resume() async {
    if (_captureState != 'paused') return;
    try {
      await _recorder.resume();
      if (mounted) setState(() => _captureState = 'recording');
    } on Object {
      if (mounted) setState(() => _error = 'Reprise impossible.');
    }
  }

  Future<void> _stop() async {
    if (_captureState != 'paused' && _captureState != 'recording') return;
    _ticker?.cancel();
    try {
      final path = await _recorder.stop();
      if (path == null || !await File(path).exists()) {
        throw const FileSystemException('No recorded audio');
      }
      if (!mounted) return;
      setState(() {
        _path = path;
        _filename = 'vocal.m4a';
        _kind = 'voice';
        _captureState = 'ready';
        _error = null;
      });
      try {
        await _player.setFilePath(path);
      } on Object {
        if (mounted) setState(() => _error = 'Aperçu vocal indisponible.');
      }
    } on Object {
      if (mounted) {
        setState(() {
          _captureState = 'error';
          _error = 'Enregistrement non enregistré.';
        });
      }
    }
  }

  Future<void> _pick() async {
    try {
      String? path;
      String? name;
      String kind = widget.mode == 'document' ? 'file' : 'image';
      if (widget.mode == 'document') {
        final selected = await NativeMediaPicker.pickDocument(
                    const ['pdf', 'txt', 'doc', 'docx'],
        );
        if (selected != null) {
          path = selected.path;
          name = selected.name;
        }
      } else {
        final selected = await NativeMediaPicker.pickImage(
          camera: widget.mode == 'camera',
          quality: 90,
          maxWidth: 2200,
        );
        path = selected?.path;
        name = selected?.name;
      }
      if (path == null || name == null) {
        if (mounted) Navigator.of(context).pop();
        return;
      }
      if (!mounted) return;
      setState(() {
        _path = path;
        _filename = name;
        _kind = kind;
        _captureState = 'ready';
      });
      // Selection is not consent to send. Let the person preview and
      // optionally add context before making a durable local intention.
    } on Object {
      if (mounted) {
        setState(() {
          _captureState = 'error';
          _error = 'Sélection indisponible. Réessayer.';
        });
      }
    }
  }

  Future<void> _send() async {
    if (_sending || _path == null || _filename == null || _kind == null) return;
    if (_requiresAudience && _selectedAudienceId == null) {
      setState(() => _error = 'Choisissez les destinataires.');
      return;
    }
    if (_requiresPoint && _selectedPointId == null) {
      setState(() => _error = 'Choisissez un échange.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final delivery = widget.repository.delivery;
      if (widget.responsePointId == null && delivery != null) {
        await delivery.queue(
          conversationId: widget.conversationId,
          mode: 'media',
          filePath: _path!,
          filename: _filename!,
          mediaKind: _kind!,
          body: _caption.text.trim(),
          pointId: _selectedPointId,
          audienceId: _selectedAudienceId,
          representedSpaceId: _representedSpace,
        );
        if (mounted) widget.onQueued?.call();
        return;
      }
      _reference ??= _newMediaReference();
      final result = widget.responsePointId == null
          ? await widget.repository.uploadMedia(
              conversationId: widget.conversationId,
              filePath: _path!,
              filename: _filename!,
              kind: _kind!,
              clientReference: _reference!,
              caption: _caption.text,
              audienceId: _selectedAudienceId,
              pointId: _selectedPointId,
              representedSpaceId: _representedSpace,
            )
          : await widget.repository.respondWithMedia(
              conversationId: widget.conversationId,
              pointId: widget.responsePointId!,
              filePath: _path!,
              filename: _filename!,
              kind: _kind!,
              clientReference: _reference!,
              representedSpaceId: _representedSpace,
            );
      if (!mounted) return;
      final id = result['point_id']?.toString();
      if (id == null || id.isEmpty) {
        throw const FormatException('Missing Point identity');
      }
      widget.onPublished(id);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Fichier non conservé pour envoi. Réessayer.');
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _cancel() async {
    if (_captureState == 'recording' || _captureState == 'paused') {
      _ticker?.cancel();
      try {
        await _recorder.cancel();
      } on Object {
        // A closed recorder still needs local capture cleanup.
      }
    }
    final path = _ownedRecordPath;
    if (path != null) {
      try {
        final file = File(path);
        if (await file.exists()) await file.delete();
      } on Object {
        // No recorded bytes are published.
      }
    }
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _caption.removeListener(_edited);
    _caption.dispose();
    if (_captureState == 'recording' || _captureState == 'paused') {
      unawaited(_recorder.cancel());
    }
    unawaited(_recorder.dispose());
    unawaited(_player.dispose());
    final path = _ownedRecordPath;
    if (path != null) {
      unawaited(File(path).delete().catchError((Object _) => File(path)));
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ready = _captureState == 'ready';
    final recording = _captureState == 'recording';
    final paused = _captureState == 'paused';
    final isVoice = widget.mode == 'voice';
    final minutes = _elapsed.inMinutes.toString().padLeft(2, '0');
    final seconds = (_elapsed.inSeconds % 60).toString().padLeft(2, '0');
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          8,
          20,
          MediaQuery.viewInsetsOf(context).bottom + 24,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                isVoice
                    ? 'Vocal'
                    : widget.mode == 'document'
                    ? 'Document'
                    : 'Photo',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 20),
              if (isVoice && (recording || paused)) ...[
                Text(
                  '$minutes:$seconds',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  children: [
                    if (recording)
                      OutlinedButton.icon(
                        onPressed: _pause,
                        icon: const Icon(Icons.pause_rounded),
                        label: const Text('Pause'),
                      ),
                    if (paused)
                      OutlinedButton.icon(
                        onPressed: _resume,
                        icon: const Icon(Icons.mic_rounded),
                        label: const Text('Reprendre'),
                      ),
                    FilledButton.tonalIcon(
                      onPressed: _stop,
                      icon: const Icon(Icons.stop_rounded),
                      label: const Text('Terminer'),
                    ),
                    TextButton(
                      onPressed: _cancel,
                      child: const Text('Annuler'),
                    ),
                  ],
                ),
              ],
              if (_captureState == 'starting')
                const Center(child: CircularProgressIndicator()),
              if (ready) ...[
                Text(_filename ?? 'Fichier'),
                if (isVoice)
                  StreamBuilder<bool>(
                    stream: _player.playingStream,
                    builder: (context, snapshot) {
                      final playing = snapshot.data == true;
                      return Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          onPressed: () async {
                            try {
                              if (playing) {
                                await _player.pause();
                              } else {
                                await _player.seek(Duration.zero);
                                unawaited(_player.play());
                              }
                            } on Object {
                              if (mounted) {
                                setState(
                                  () =>
                                      _error = 'Lecture du vocal indisponible.',
                                );
                              }
                            }
                          },
                          icon: Icon(
                            playing
                                ? Icons.pause_rounded
                                : Icons.play_arrow_rounded,
                          ),
                          label: Text(playing ? 'Pause' : 'Écouter'),
                        ),
                      );
                    },
                  ),
                const SizedBox(height: 12),
                TextField(
                  controller: _caption,
                  maxLength: 5000,
                  decoration: const InputDecoration(
                    labelText: 'Légende (facultative)',
                    border: OutlineInputBorder(),
                  ),
                ),
                if (_requiresPoint)
                  DropdownButtonFormField<String>(
                    initialValue: _selectedPointId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Échange',
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      for (final row in _rows('exchange_targets'))
                        DropdownMenuItem(
                          value: row['id']?.toString(),
                          child: Text(row['title']?.toString() ?? 'Échange'),
                        ),
                    ],
                    onChanged: _sending
                        ? null
                        : (value) => setState(() {
                            _selectedPointId = value;
                            _reference = null;
                          }),
                  ),
                if (_requiresAudience)
                  DropdownButtonFormField<String>(
                    initialValue: _selectedAudienceId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Destinataires',
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      for (final row in _rows('audiences'))
                        DropdownMenuItem(
                          value: row['id']?.toString(),
                          child: Text(row['label']?.toString() ?? 'Audience'),
                        ),
                    ],
                    onChanged: _sending
                        ? null
                        : (value) => setState(() {
                            _selectedAudienceId = value;
                            _reference = null;
                          }),
                  ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    TextButton(
                      onPressed: _sending ? null : _cancel,
                      child: const Text('Annuler'),
                    ),
                    const Spacer(),
                    FilledButton(
                      key: const Key('conversation-media-send'),
                      onPressed: _sending ? null : _send,
                      child: Text(_sending ? 'Envoi…' : 'Envoyer'),
                    ),
                  ],
                ),
              ],
              if (_captureState == 'error' && !_sending)
                TextButton(
                  onPressed: isVoice ? _startRecord : _pick,
                  child: const Text('Réessayer'),
                ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              if (!ready && !recording && !paused)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: _cancel,
                    child: const Text('Fermer'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
