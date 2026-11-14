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
    required this.onPreview,
    required this.onClose,
    this.permissions = const PermissionHandlerGateway(),
    this.channel = const MethodChannel('makolo/native_dictation'),
  });

  final ValueChanged<String> onText;
  final ValueChanged<String> onPreview;
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
      if (available) unawaited(_start());
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
        setState(() => _status = 'Un instant…');
        return;
      case 'partial':
      case 'final':
        if (next.isNotEmpty) {
          _text.value = TextEditingValue(
            text: next,
            selection: TextSelection.collapsed(offset: next.length),
          );
          widget.onPreview(next);
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
          _error = 'Aucune parole reconnue. Réessayez ou écrivez.';
        });
        return;
      case 'error':
        setState(() {
          _active = false;
          _busy = false;
          _error = 'La dictée s’est interrompue. Réessayez ou écrivez votre demande.';
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
      if (!mounted) return;
      await widget.channel.invokeMethod<void>('start');
      if (!mounted) {
        try {
          await widget.channel.invokeMethod<void>('cancel');
        } on Object {
          // The native recognizer may already have stopped.
        }
        return;
      }
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
          _error = 'Le micro n’a pas démarré. Vous pouvez réessayer ou écrire.';
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
          _error = 'Impossible de terminer la dictée.';
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
    final scheme = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              if (_active)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(Icons.mic_rounded, color: scheme.primary),
                )
              else
                const Padding(
                  padding: EdgeInsets.only(right: 8),
                  child: Icon(Icons.mic_none_outlined),
                ),
              Expanded(
                child: Text(
                  _checking
                      ? 'Microphone…'
                      : _active
                      ? 'Je vous écoute'
                      : _busy
                      ? 'Un instant…'
                      : _text.text.isNotEmpty
                      ? 'Texte prêt à corriger'
                      : _available
                      ? 'Dicter'
                      : 'Dictée indisponible',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              if (_active)
                IconButton(
                  tooltip: 'Terminer la dictée',
                  onPressed: _busy ? null : () => unawaited(_stop()),
                  icon: const Icon(Icons.stop_circle_outlined),
                )
              else if (!_checking && _available)
                IconButton(
                  tooltip: 'Recommencer la dictée',
                  onPressed: _busy ? null : () => unawaited(_start()),
                  icon: const Icon(Icons.mic_none_rounded),
                ),
              if (_text.text.trim().isNotEmpty && !_active)
                IconButton.filledTonal(
                  tooltip: 'Garder la dictée et corriger le texte',
                  onPressed: _busy
                      ? null
                      : () => widget.onText(_text.text.trim()),
                  icon: const Icon(Icons.check_rounded),
                ),
              IconButton(
                tooltip: 'Annuler la dictée',
                onPressed: () {
                  unawaited(_cancelNative());
                  widget.onClose();
                },
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 3, 8, 4),
              child: Text(
                _error!,
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(color: scheme.error),
              ),
            ),
        ],
      ),
    );
  }
}
