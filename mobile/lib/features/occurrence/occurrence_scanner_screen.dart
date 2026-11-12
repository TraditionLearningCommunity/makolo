import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';
import '../../platform/scanner/code_scanner.dart';

/// Secure, owner-backed Occurrence Scanner. Never stores or logs raw QR data.
/// Camera decoding is optional: manual entry remains available.
class OccurrenceScannerScreen extends StatefulWidget {
  const OccurrenceScannerScreen({
    super.key,
    required this.runtime,
    required this.occurrenceId,
    this.actorSpaceId,
  });

  final AppRuntime runtime;
  final String occurrenceId;
  final String? actorSpaceId;

  @override
  State<OccurrenceScannerScreen> createState() =>
      _OccurrenceScannerScreenState();
}

class _OccurrenceScannerScreenState extends State<OccurrenceScannerScreen>
    with WidgetsBindingObserver {
  final TextEditingController _code = TextEditingController();
  Map<String, dynamic>? _context;
  Map<String, dynamic>? _result;
  bool _busy = false;
  bool _checking = false;
  bool _camera = false;
  bool _confirming = false;
  bool _needsReview = false;
  bool _denied = false;
  int _epoch = 0;
  int _attempt = 0;

  bool get _actorValid {
    final actor = widget.runtime.actorContext?.value;
    final space = widget.actorSpaceId;
    return space == null
        ? actor is! SpaceActorContext
        : actor is SpaceActorContext && actor.space.id == space;
  }

  String get _contextPath =>
      'api/v1/scanner/occurrences/${widget.occurrenceId}/context/';
  String get _controlPath =>
      'api/v1/scanner/occurrences/${widget.occurrenceId}/control/';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.runtime.actorContext?.addListener(_onActorChanged);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant OccurrenceScannerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.occurrenceId != widget.occurrenceId ||
        oldWidget.actorSpaceId != widget.actorSpaceId ||
        oldWidget.runtime != widget.runtime) {
      _onActorChanged();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      // Resume always obtains a fresh owner check, even if an older request
      // has not completed yet.
      _epoch++;
      _checking = false;
      _code.clear();
      unawaited(_load());
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _epoch++;
      _code.clear();
      if (mounted) {
        setState(() {
          _camera = false;
          _context = null;
          _result = null;
          _busy = false;
          _confirming = false;
          _checking = false;
        });
      }
    }
  }

  void _onActorChanged() {
    _epoch++;
    _code.clear();
    if (!mounted) return;
    setState(() {
      _context = null;
      _result = null;
      _camera = false;
      _checking = false;
      _busy = false;
      _confirming = false;
      _needsReview = false;
      _denied = false;
    });
    if (_actorValid) unawaited(_load());
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    WidgetsBinding.instance.removeObserver(this);
    _code.dispose();
    super.dispose();
  }

  Future<void> _load({bool resumeAfterReview = false}) async {
    if (!_actorValid || _checking) return;
    final epoch = ++_epoch;
    setState(() {
      _checking = true;
      _denied = false;
      _context = null;
      _camera = false;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Service Scanner indisponible');
      final result = (await api.get(_contextPath)).jsonObject();
      final payload = result['data'];
      if (payload is! Map) throw const FormatException('Contexte absent');
      final data = Map<String, dynamic>.from(payload);
      final identity = data['identity'];
      final links = data['links'];
      final space = data['space'];
      if (identity is! Map ||
          identity['id']?.toString() != widget.occurrenceId ||
          links is! Map ||
          links['scan'] != '/$_controlPath' ||
          !(data['capabilities'] is List &&
              (data['capabilities'] as List).contains('scan')) ||
          (widget.actorSpaceId != null &&
              (space is! Map ||
                  space['id']?.toString() != widget.actorSpaceId))) {
        throw const FormatException('Contexte Scanner incohérent');
      }
      if (!mounted || epoch != _epoch || !_actorValid) return;
      setState(() {
        _context = data;
        // A fresh mandate check is not evidence of an earlier scan result.
        // Only explicit operator acknowledgement can release this hold.
        if (resumeAfterReview) {
          _needsReview = false;
          _result = null;
        }
      });
    } on Object catch (error) {
      if (!mounted || epoch != _epoch) return;
      setState(() {
        _denied =
            error is MakoloApiError &&
            const {401, 403, 404}.contains(error.statusCode);
        _context = null;
      });
    } finally {
      if (mounted && epoch == _epoch) setState(() => _checking = false);
    }
  }

  Future<void> _offerToken(String raw, {bool fromCamera = false}) async {
    final token = raw.trim();
    if (token.isEmpty ||
        token.length > 1024 ||
        _busy ||
        _confirming ||
        _checking ||
        _needsReview ||
        !_actorValid ||
        _context == null) {
      return;
    }
    final revision = _epoch;
    setState(() {
      _confirming = !fromCamera;
      _camera = false;
    });
    // Starting the camera is the deliberate scan gesture. Avoid one modal
    // per attendee; manual entry still requires explicit confirmation.
    if (fromCamera) {
      await _submit(token);
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirmer le contrôle'),
        content: const Text(
          'Contrôler ce justificatif maintenant ? '
          'Une acceptation peut consommer un accès individuel.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Contrôler'),
          ),
        ],
      ),
    );
    if (!mounted || _epoch != revision || !_actorValid) return;
    setState(() => _confirming = false);
    if (confirmed != true) return;
    await _submit(token);
  }

  Future<void> _submit(String token) async {
    final currentEpoch = _epoch;
    if (_busy || _checking || _needsReview || _context == null || !_actorValid)
      return;
    setState(() {
      _busy = true;
      _needsReview = false;
      _result = null;
    });
    try {
      // Reconfirm owner authority immediately before every sensitive mutation.
      final api = widget.runtime.api;
      if (api == null) throw StateError('Service Scanner indisponible');
      final verified = (await api.get(_contextPath)).jsonObject()['data'];
      if (verified is! Map ||
          (verified['identity'] is! Map ||
              (verified['identity'] as Map)['id']?.toString() !=
                  widget.occurrenceId) ||
          (verified['capabilities'] is! List ||
              !(verified['capabilities'] as List).contains('scan')) ||
          (verified['links'] is! Map ||
              (verified['links'] as Map)['scan'] != '/$_controlPath') ||
          (widget.actorSpaceId != null &&
              (verified['space'] is! Map ||
                  (verified['space'] as Map)['id']?.toString() !=
                      widget.actorSpaceId))) {
        throw StateError('Mandat Scanner à renouveler');
      }
      final result = (await api.post(
        _controlPath,
        body: {
          'token': token,
          'client_reference':
              'mobile-${DateTime.now().microsecondsSinceEpoch}-${++_attempt}',
        },
      )).jsonObject();
      if (!mounted || _epoch != currentEpoch || !_actorValid) return;
      setState(() => _result = result);
    } on Object catch (error) {
      if (!mounted || _epoch != currentEpoch) return;
      setState(() {
        // A client-side validation refusal is known; a lost response is not.
        final invalidRequest =
            error is MakoloApiError &&
            const {400, 422}.contains(error.statusCode);
        _needsReview = !invalidRequest;
        _result = {
          // A missing response cannot establish either acceptance or refusal.
          'accepted': invalidRequest ? false : null,
          'message':
              error is MakoloApiError &&
                  const {401, 403, 404}.contains(error.statusCode)
              ? 'Votre autorisation de contrôle doit être revérifiée.'
              : invalidRequest
              ? 'Code refusé. Corrigez la saisie avant un nouveau contrôle.'
              : 'Contrôle non confirmé. Vérifiez la connexion avant un nouvel essai.',
        };
        if (error is MakoloApiError &&
            const {401, 403, 404}.contains(error.statusCode)) {
          _context = null;
          _denied = true;
        }
      });
    } finally {
      _code.clear();
      if (mounted && _epoch == currentEpoch) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _context;
    final occurrence = data?['occurrence'];
    final title = occurrence is Map
        ? occurrence['label']?.toString() ?? 'Contrôle d’accès'
        : 'Contrôle d’accès';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scanner'),
        actions: [
          IconButton(
            tooltip: 'Vérifier les autorisations',
            onPressed: _busy || _checking ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: !_actorValid || _denied
          ? const Center(
              child: Text(
                'Ce Scanner n’est plus autorisé dans le contexte actif.',
              ),
            )
          : data == null
          ? Center(
              child: _checking
                  ? const CircularProgressIndicator()
                  : TextButton(
                      onPressed: _load,
                      child: const Text('Réessayer'),
                    ),
            )
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(title, style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                const Text('Autorisation confirmée pour cette Occurrence.'),
                if (_checking || _busy) const LinearProgressIndicator(),
                const SizedBox(height: 18),
                if (_result != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          Icon(
                            _result!['accepted'] == true
                                ? Icons.check_circle_outline
                                : Icons.warning_amber_outlined,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              _result!['message']?.toString() ??
                                  'Résultat du contrôle à vérifier.',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                MakoloActionButton(
                  onPressed: _busy || _checking || _confirming || _needsReview
                      ? null
                      : () => setState(() => _camera = !_camera),
                  icon: _camera ? Icons.close : Icons.qr_code_scanner_rounded,
                  label: _camera ? 'Fermer la caméra' : 'Scanner un QR',
                  appearance: MakoloActionAppearance.primary,
                  phase: _busy || _confirming
                      ? MakoloActionPhase.processing
                      : _needsReview
                      ? MakoloActionPhase.failed
                      : _checking
                      ? MakoloActionPhase.unavailable
                      : MakoloActionPhase.available,
                ),
                if (_camera) ...[
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 280,
                    child: MakoloCodeScanner(
                      onCode: (code) {
                        if (_camera && !_busy && !_needsReview) {
                          unawaited(_offerToken(code.value, fromCamera: true));
                        }
                      },
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                TextField(
                  controller: _code,
                  enabled: !_busy && !_checking,
                  decoration: const InputDecoration(
                    labelText: 'Saisie manuelle du justificatif',
                    hintText: 'Code de contrôle',
                    border: OutlineInputBorder(),
                  ),
                  maxLines: 1,
                  autocorrect: false,
                  enableSuggestions: false,
                  obscureText: true,
                ),
                const SizedBox(height: 12),
                MakoloActionButton(
                  onPressed: _busy || _checking || _confirming || _needsReview
                      ? null
                      : () => _offerToken(_code.text),
                  label: 'Contrôler ce code',
                  icon: Icons.verified_outlined,
                  phase: _busy || _confirming
                      ? MakoloActionPhase.processing
                      : _needsReview
                      ? MakoloActionPhase.failed
                      : _checking
                      ? MakoloActionPhase.unavailable
                      : MakoloActionPhase.available,
                ),
                if (_needsReview) ...[
                  const SizedBox(height: 8),
                  const Text(
                    'Résultat non confirmé. Consultez les contrôles existants '
                    'avant de reprendre. Un nouveau scan n’est pas un moyen '
                    'de confirmer la tentative précédente.',
                  ),
                  MakoloActionButton(
                    label: 'Contrôle précédent vérifié : reprendre',
                    icon: Icons.refresh_rounded,
                    onPressed: _checking || _busy
                        ? null
                        : () => _load(resumeAfterReview: true),
                  ),
                ],
                const SizedBox(height: 16),
                const Text(
                  'Le code n’est pas conservé sur cet écran. '
                  'Un contrôle déjà accepté peut refuser un nouveau passage.',
                ),
              ],
            ),
    );
  }
}
