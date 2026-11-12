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

class _MarkVoiceCaptureState extends State<MarkVoiceCapture> {
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
      await widget.store.stagingDirectory.create(recursive: true);
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
    if (staged != null && !_adopted) await widget.store.remove(staged.fileId);
    if (mounted) widget.onClose();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    unawaited(_recorder.cancel().catchError((Object _) {}).then((_) => _recorder.dispose()));
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
    final time = '${(_seconds ~/ 60).toString().padLeft(2, '0')}:'
        '${(_seconds % 60).toString().padLeft(2, '0')}';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Enregistrement audio', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            const Text(
              'Cet audio reste sur cet appareil. Il ne sera ni transcrit '
              'ni transmis automatiquement.',
            ),
            if (_recording) ...[
              const SizedBox(height: 8),
              Text(_paused ? 'En pause · $time' : 'En cours · $time'),
            ],
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (!_recording && _staged == null)
                  MakoloActionButton(
                    label: 'Enregistrer',
                    icon: Icons.mic,
                    busy: _busy,
                    onPressed: _busy ? null : () => unawaited(_start()),
                  ),
                if (_recording) ...[
                  MakoloActionButton(
                    label: _paused ? 'Reprendre' : 'Pause',
                    icon: _paused ? Icons.play_arrow : Icons.pause,
                    onPressed: _busy ? null : () => unawaited(_togglePause()),
                  ),
                  MakoloActionButton(
                    label: 'Terminer',
                    icon: Icons.stop,
                    busy: _busy,
                    onPressed: _busy ? null : () => unawaited(_stop()),
                  ),
                ],
                if (_staged != null) ...[
                  MakoloActionButton(
                    label: 'Écouter',
                    icon: Icons.play_arrow,
                    onPressed: _busy ? null : () => unawaited(_play()),
                  ),
                  MakoloActionButton(
                    label: 'Ajouter au brouillon',
                    icon: Icons.check,
                    busy: _busy,
                    onPressed: _busy ? null : () => unawaited(_keep()),
                  ),
                ],
                MakoloActionButton(
                  label: 'Annuler',
                  appearance: MakoloActionAppearance.quiet,
                  onPressed: _busy ? null : () => unawaited(_cancel()),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
