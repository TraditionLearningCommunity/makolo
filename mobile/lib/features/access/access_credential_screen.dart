import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import '../../platform/scanner/qr_renderer.dart';
import 'access_repository.dart';

class AccessCredentialScreen extends StatefulWidget {
  const AccessCredentialScreen({
    super.key,
    required this.accessId,
    required this.credentialPath,
    required this.repository,
    this.title = 'QR d’accès',
  });

  final String accessId;
  final String? credentialPath;
  final AccessRepository repository;
  final String title;

  @override
  State<AccessCredentialScreen> createState() => _AccessCredentialScreenState();
}

class _AccessCredentialScreenState extends State<AccessCredentialScreen>
    with WidgetsBindingObserver {
  AccessCredentialData? _credential;
  Object? _error;
  bool _loading = false;
  int _generation = 0;
  Timer? _expiryTimer;

  void _setCredential(AccessCredentialData? next) {
    _expiryTimer?.cancel();
    _expiryTimer = null;
    if (!mounted) return;
    setState(() => _credential = next);
    final deadline = next?.offlineUntil;
    if (deadline == null) return;
    final remaining = deadline.toUtc().difference(DateTime.now().toUtc());
    if (remaining <= Duration.zero) {
      setState(() => _credential = null);
      return;
    }
    _expiryTimer = Timer(remaining, () {
      if (!mounted) return;
      // The offline presentation lease has ended. A fresh owner response
      // is required; never leave the old QR visible in a resumed view.
      _generation++;
      _loading = false;
      setState(() {
        _credential = null;
        _error = StateError('AccessCredential display permission expired');
      });
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant AccessCredentialScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.accessId != widget.accessId ||
        oldWidget.credentialPath != widget.credentialPath ||
        oldWidget.repository != widget.repository) {
      _generation++;
      _expiryTimer?.cancel();
      _loading = false;
      _credential = null;
      _error = null;
      unawaited(_load());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_load());
      return;
    }
    // A pending request must not redraw a secret after the app backgrounds.
    _generation++;
    _expiryTimer?.cancel();
    _loading = false;
    if (mounted && (_credential != null || _error != null)) {
      setState(() {
        _credential = null;
        _error = null;
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _generation++;
    _expiryTimer?.cancel();
    _credential = null;
    super.dispose();
  }

  Future<void> _load() async {
    if (_loading) return;
    final generation = ++_generation;
    final requestedAccess = widget.accessId;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // Read the OS-protected copy first. No re-acquisition is required to
      // show a previously granted, not-yet-expired display permission.
      AccessCredentialData? retained;
      try {
        retained = await widget.repository.readRetainedCredential(
          requestedAccess,
        );
      } on Object {
        // A missing/unavailable OS vault must not block an online-only QR.
        // The secret is never copied to an unprotected alternative store.
      }
      if (!mounted ||
          _generation != generation ||
          widget.accessId != requestedAccess) {
        return;
      }
      if (retained != null) {
        _setCredential(retained);
      }
      final path =
          widget.credentialPath ??
          await widget.repository.readKnownCredentialPath(requestedAccess);
      if (path == null) {
        if (retained == null) {
          throw StateError('No owner credential link on this device');
        }
        return;
      }
      final fresh = await widget.repository.fetchCredential(
        accessId: requestedAccess,
        path: path,
      );
      if (!mounted ||
          _generation != generation ||
          widget.accessId != requestedAccess) {
        return;
      }
      _setCredential(fresh);
    } on Object catch (error) {
      if (!mounted ||
          _generation != generation ||
          widget.accessId != requestedAccess) {
        return;
      }
      final revoked =
          error is MakoloApiError &&
          (error.statusCode == 403 || error.statusCode == 404);
      setState(() {
        if (revoked) {
          _expiryTimer?.cancel();
          _credential = null;
        }
        _error = error;
      });
    } finally {
      if (mounted && _generation == generation) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final credential = _credential;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Actualiser',
            icon: Icons.refresh_rounded,
            onPressed: _loading ? null : _load,
            phase: _loading
                ? MakoloActionPhase.processing
                : _error != null
                ? MakoloActionPhase.failed
                : MakoloActionPhase.available,
          ),
        ],
      ),
      body: SafeArea(
        child: switch ((credential, _loading, _error)) {
          (null, true, _) => const MakoloLoadingState(
            label: 'Chargement du QR…',
          ),
          (null, false, _) when _error != null => MakoloErrorState(
            message:
                'Le QR ne peut pas être chargé. '
                'Le droit déjà reçu reste consultable dans Mes accès. '
                'La présentation hors ligne nécessite une copie sécurisée '
                'explicitement autorisée par Access.',
            onRetry: _load,
          ),
          (final value?, _, _) when value.credentialType != 'qr' =>
            const MakoloEmptyState(
              title: 'Représentation non prise en charge',
              body: 'Ce justificatif ne peut pas être affiché ici.',
              icon: Icons.lock_outline_rounded,
            ),
          (final value?, _, _) => _CredentialQr(credential: value),
          _ => const MakoloLoadingState(label: 'Chargement du QR…'),
        },
      ),
    );
  }
}

class _CredentialQr extends StatelessWidget {
  const _CredentialQr({required this.credential});

  final AccessCredentialData credential;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(MakoloSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Semantics(
              image: true,
              label: 'QR d’accès',
              child: ExcludeSemantics(
                child: MakoloQrView(payload: credential.payload, size: 260),
              ),
            ),
            const SizedBox(height: MakoloSpacing.xl),
            Text(
              'Présentez ce QR uniquement au point de contrôle prévu.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            if (credential.locallyRetained) ...[
              const SizedBox(height: MakoloSpacing.md),
              Text(
                'Copie protégée reçue précédemment. '
                'Son affichage hors connexion ne prouve pas la validité '
                'actuelle : le contrôle reste effectué par Access.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
