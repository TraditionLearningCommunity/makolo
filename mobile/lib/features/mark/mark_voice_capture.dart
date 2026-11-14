import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:record/record.dart';

import '../../data/files/profile_file_store.dart';
import '../../design/action_controls.dart';
import '../../platform/permissions/permission_gateway.dart';

/// Android voice *file* capture. There is no claim of speech recognition:
/// the captured audio remains a private Profile-scoped Mark draft attachment.
class MarkVoiceCapture extends StatefulWidget {
  const MarkVoiceCapture({
    super.key,
    required this.store,
    required this.owner,
    required this.onCaptured,
    required this.onClose,
  });

  final ProfileFileStore store;
  final String owner;
  final Future<void> Function(StoredLocalFile file) onCaptured;
  final VoidCallback onClose;

  @override
  State<MarkVoiceCapture> createState() => _MarkVoiceCaptureState();
}

class _MarkVoiceCaptureState extends State<MarkVoiceCapture>
    with WidgetsBindingObserver {
  static const maxSeconds = 120;
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  Timer? _ticker;
  StoredLocalFile? _staged;
  String? _recordingPath;
  bool _recording = false;
  bool _paused = false;
  bool _busy = false;
  bool _adopted = false;
  int _seconds = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_start());
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed &&
        _recording &&
        !_paused &&
        !_busy) {
      unawaited(_togglePause());
    }
  }

  Future<void> _start() async {
    if (_busy || _recording || _staged != null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      const permissions = PermissionHandlerGateway();
      final decision = await permissions.requestWhenNeeded(
        MakoloPermission.microphone,
      );
      if (!decision.permitsCapability || !await _recorder.hasPermission()) {
        throw StateError('Microphone non autorisé sur cet appareil.');
      }
      if (!mounted) return;
      await widget.store.stagingDirectory.create(recursive: true);
      if (!mounted) return;
      final path =
          '${widget.store.stagingDirectory.path}/stage-mark-voice-${DateTime.now().microsecondsSinceEpoch}.m4a';
      _recordingPath = path;
      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.aacLc),
        path: path,
      );
      if (!mounted) {
        await _recorder.cancel();
        await _removeTemporaryFile();
        return;
      }
      setState(() {
        _recording = true;
        _paused = false;
        _busy = false;
      });
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted || !_recording || _paused) return;
        setState(() => _seconds++);
        if (_seconds >= maxSeconds) unawaited(_stop());
      });
    } on Object {
      if (mounted) {
        setState(() {
          _busy = false;
          _recording = false;
          _error = 'L’enregistrement n’a pas pu démarrer. Vous pouvez écrire votre demande.';
        });
      }
      await _removeTemporaryFile();
    }
  }

  Future<void> _togglePause() async {
    if (_busy || !_recording) return;
    setState(() => _busy = true);
    try {
      if (_paused) {
        await _recorder.resume();
      } else {
        await _recorder.pause();
      }
      if (!mounted) return;
      setState(() {
        _paused = !_paused;
        _busy = false;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = 'Impossible de changer l’état de l’enregistrement.';
        });
      }
    }
  }

  Future<void> _stop() async {
    if (_busy || !_recording) return;
    _ticker?.cancel();
    setState(() => _busy = true);
    try {
      final path = await _recorder.stop();
      if (path == null || path.isEmpty) {
        throw const FileSystemException('Audio capture is empty.');
      }
      _recordingPath = path;
      final staged = await widget.store.stage(
        fileId: 'mark-voice-${DateTime.now().microsecondsSinceEpoch}',
        sourcePath: path,
        owner: widget.owner,
        purpose: 'mark_intake',
        sensitivity: 'private',
      );
      await _removeTemporaryFile();
      if (!mounted) {
        await widget.store.remove(staged.fileId);
        return;
      }
      setState(() {
        _staged = staged;
        _recording = false;
        _paused = false;
        _busy = false;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _recording = false;
          _paused = false;
          _busy = false;
          _error = 'Impossible de conserver cet enregistrement.';
        });
      }
      await _removeTemporaryFile();
    }
  }

  Future<void> _play() async {
    final file = _staged;
    if (file == null || _busy) return;
    try {
      await _player.setFilePath(file.path);
      await _player.play();
    } on Object {
      if (mounted) {
        setState(() => _error = 'Impossible de lire cet enregistrement.');
      }
    }
  }

  Future<void> _keep() async {
    final file = _staged;
    if (file == null || _busy) return;
    setState(() => _busy = true);
    try {
      // The parent may remove this widget immediately after saving the draft.
      // Transfer ownership before invoking its callback.
      _adopted = true;
      await widget.onCaptured(file);
    } on Object {
      _adopted = false;
      if (mounted) {
        setState(() {
          _busy = false;
          _error = 'Impossible d’enregistrer cette pièce dans le brouillon.';
        });
      }
    }
  }

  Future<void> _removeTemporaryFile() async {
    final path = _recordingPath;
    _recordingPath = null;
    if (path == null) return;
    final file = File(path);
    try {
      if (await file.exists()) await file.delete();
    } on FileSystemException {
      // Profile-scoped stage-* leftovers are handled by staging cleanup.
    }
  }

  Future<void> _cancel() async {
    if (_busy) return;
    _ticker?.cancel();
    setState(() => _busy = true);
    try {
      await _recorder.cancel();
    } on Object {
      // A native interruption can already have closed the recorder.
    }
    await _removeTemporaryFile();
    final staged = _staged;
    if (staged != null && !_adopted) {
      try {
        await widget.store.remove(staged.fileId);
      } on Object {
        // The same file record remains Profile-scoped for later cleanup.
      }
    }
    if (mounted) widget.onClose();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _ticker?.cancel();
    unawaited(
      _recorder
          .cancel()
          .catchError((Object _) {})
          .then((_) => _recorder.dispose()),
    );
    unawaited(_player.dispose());
    unawaited(_removeTemporaryFile());
    final staged = _staged;
    if (staged != null && !_adopted) {
      unawaited(widget.store.remove(staged.fileId));
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final time =
        '${(_seconds ~/ 60).toString().padLeft(2, '0')}:'
        '${(_seconds % 60).toString().padLeft(2, '0')}';
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(
                _recording && !_paused
                    ? Icons.fiber_manual_record
                    : Icons.graphic_eq,
                color: _recording && !_paused ? scheme.error : scheme.primary,
                size: 19,
              ),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  _recording
                      ? (_paused ? 'En pause · $time' : 'En cours · $time')
                      : _staged != null
                      ? 'Audio · $time'
                      : _busy
                      ? 'Microphone…'
                      : 'Audio',
                  style: Theme.of(context).textTheme.bodyMedium,
                  maxLines: 1,
                ),
              ),
              if (!_recording && _staged == null && !_busy)
                IconButton(
                  tooltip: 'Enregistrer',
                  onPressed: () => unawaited(_start()),
                  icon: const Icon(Icons.mic_rounded),
                ),
              if (_recording) ...[
                IconButton(
                  tooltip: _paused ? 'Reprendre' : 'Pause',
                  onPressed: _busy ? null : () => unawaited(_togglePause()),
                  icon: Icon(_paused ? Icons.play_arrow : Icons.pause_rounded),
                ),
                IconButton.filledTonal(
                  tooltip: 'Terminer l’enregistrement',
                  onPressed: _busy ? null : () => unawaited(_stop()),
                  icon: const Icon(Icons.stop_rounded),
                ),
              ],
              if (_staged != null) ...[
                IconButton(
                  tooltip: 'Écouter l’audio',
                  onPressed: _busy ? null : () => unawaited(_play()),
                  icon: const Icon(Icons.play_arrow_rounded),
                ),
                IconButton.filledTonal(
                  tooltip: 'Garder l’audio',
                  onPressed: _busy ? null : () => unawaited(_keep()),
                  icon: const Icon(Icons.check_rounded),
                ),
              ],
              IconButton(
                tooltip: 'Annuler l’enregistrement',
                onPressed: _busy ? null : () => unawaited(_cancel()),
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(left: 8, top: 4, bottom: 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _error!,
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(color: scheme.error),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
