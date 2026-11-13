import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../design/action_controls.dart';
import '../../platform/permissions/permission_gateway.dart';

/// Conditional Android dictation, never a guaranteed offline transcription.
/// The OS owns the recognizer; no transcript is uploaded by Mark itself.
class MarkDictationCapture extends StatefulWidget {
  const MarkDictationCapture({
    super.key,
    required this.onText,
    required this.onClose,
    this.permissions = const PermissionHandlerGateway(),
    this.channel = const MethodChannel('makolo/native_dictation'),
  });

  final ValueChanged<String> onText;
  final VoidCallback onClose;
  final PermissionGateway permissions;
  final MethodChannel channel;

  @override
  State<MarkDictationCapture> createState() => _MarkDictationCaptureState();
}

class _MarkDictationCaptureState extends State<MarkDictationCapture>
    with WidgetsBindingObserver {
  final TextEditingController _text = TextEditingController();
  bool _available = false;
  bool _checking = true;
  bool _active = false;
  bool _busy = false;
  String? _error;
  String? _status;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.channel.setMethodCallHandler(_onSpeechEvent);
    unawaited(_check());
  }

  Future<void> _check() async {
    bool available = false;
    try {
      available = await widget.channel.invokeMethod<bool>('available') == true;
    } on Object {
      available = false;
    }
    if (mounted) {
      setState(() {
        _available = available;
        _checking = false;
      });
    }
  }

  Future<void> _onSpeechEvent(MethodCall call) async {
    if (call.method != 'speechEvent' || !mounted) return;
    final args = call.arguments;
    if (args is! Map) return;
    final type = args['type']?.toString();
    final next = args['text']?.toString() ?? '';
    switch (type) {
      case 'listening':
        setState(() => _status = 'Écoute en cours');
        return;
      case 'processing':
        setState(() => _status = 'Reconnaissance en cours');
        return;
      case 'partial':
      case 'final':
        if (next.isNotEmpty) {
          _text.value = TextEditingValue(
            text: next,
            selection: TextSelection.collapsed(offset: next.length),
          );
        }
        if (type == 'final') {
          setState(() {
            _active = false;
            _busy = false;
            _status = 'Vous pouvez modifier le texte avant de continuer.';
          });
        }
        return;
      case 'empty':
        setState(() {
          _active = false;
          _busy = false;
          _error = 'Aucune parole reconnue. Vous pouvez réessayer ou écrire.';
        });
        return;
      case 'error':
        setState(() {
          _active = false;
          _busy = false;
          _error = 'La dictée système est indisponible ou a été interrompue.';
        });
        return;
      default:
        return;
    }
  }

  Future<void> _start() async {
    if (_busy || _active || !_available) return;
    setState(() {
      _busy = true;
      _error = null;
      _status = null;
    });
    try {
      final permission = await widget.permissions.requestWhenNeeded(
        MakoloPermission.microphone,
      );
      if (!permission.permitsCapability) {
        throw StateError('Microphone refused');
      }
      await widget.channel.invokeMethod<void>('start');
      if (!mounted) return;
      setState(() {
        _busy = false;
        _active = true;
        _status = 'Parlez naturellement';
      });
    } on Object {
      if (mounted) {
        setState(() {
          _busy = false;
          _active = false;
          _error =
              'Impossible de démarrer la dictée. La saisie reste disponible.';
        });
      }
    }
  }

  Future<void> _stop() async {
    if (_busy || !_active) return;
    setState(() {
      _busy = true;
      _status = 'Fin de la dictée…';
    });
    try {
      await widget.channel.invokeMethod<void>('stop');
      // Results or a recognition error will end the pending state.
    } on Object {
      if (mounted) {
        setState(() {
          _busy = false;
          _active = false;
          _error = 'Impossible de terminer la reconnaissance.';
        });
      }
    }
  }

  Future<void> _cancelNative() async {
    try {
      await widget.channel.invokeMethod<void>('cancel');
    } on Object {
      // Native recognizer may already have exited.
    }
    if (mounted) {
      setState(() {
        _active = false;
        _busy = false;
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && _active) {
      unawaited(_cancelNative());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.channel.setMethodCallHandler(null);
    unawaited(
      widget.channel.invokeMethod<void>('cancel').catchError((Object _) {}),
    );
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Dictée', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            const Text(
              'La reconnaissance dépend du téléphone, de sa langue '
              'et parfois du réseau ou d’un service système. '
              'Aucun moteur IA Makolo n’est nécessaire.',
            ),
            if (_status != null) ...[
              const SizedBox(height: 8),
              Text(_status!, semanticsLabel: _status),
            ],
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              controller: _text,
              minLines: 2,
              maxLines: 5,
              readOnly: _active,
              decoration: const InputDecoration(
                labelText: 'Texte reconnu, modifiable',
                hintText: 'Votre dictée apparaîtra ici',
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (!_active)
                  MakoloActionButton(
                    label: _checking ? 'Vérification…' : 'Commencer',
                    icon: Icons.mic_none,
                    onPressed: _checking || !_available || _busy
                        ? null
                        : () => unawaited(_start()),
                    appearance: MakoloActionAppearance.secondary,
                  ),
                if (_active)
                  MakoloActionButton(
                    label: 'Terminer',
                    icon: Icons.stop_circle_outlined,
                    busy: _busy,
                    onPressed: _busy ? null : () => unawaited(_stop()),
                  ),
                MakoloActionButton(
                  label: 'Utiliser ce texte',
                  icon: Icons.check,
                  onPressed: _active || _text.text.trim().isEmpty
                      ? null
                      : () => widget.onText(_text.text.trim()),
                  appearance: MakoloActionAppearance.primary,
                ),
                MakoloActionButton(
                  label: 'Annuler',
                  onPressed: () {
                    unawaited(_cancelNative());
                    widget.onClose();
                  },
                  appearance: MakoloActionAppearance.quiet,
                ),
              ],
            ),
            if (!_checking && !_available)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                  'La dictée n’est pas disponible ici. Vous pouvez écrire '
                  'ou conserver un enregistrement audio.',
                ),
              ),
          ],
        ),
      ),
    );
  }
}
