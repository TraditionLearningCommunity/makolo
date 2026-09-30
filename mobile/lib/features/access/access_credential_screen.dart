import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
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
  final String credentialPath;
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
    _credential = null;
    super.dispose();
  }

  Future<void> _load() async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final credential = await widget.repository.fetchCredential(
        accessId: widget.accessId,
        path: widget.credentialPath,
      );
      if (!mounted) return;
      setState(() => _credential = credential);
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _credential = null;
        _error = error;
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final credential = _credential;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: SafeArea(
        child: switch ((credential, _loading, _error)) {
          (null, true, _) => const MakoloLoadingState(
            label: 'Chargement du QR…',
          ),
          (null, false, final error?) => MakoloErrorState(
            message: 'Le QR ne peut pas être affiché pour le moment.',
            onRetry: _load,
          ),
          (final value?, _, _) when value.credentialType != 'qr' =>
            const MakoloEmptyState(
              title: 'Représentation non prise en charge',
              body: 'Cette représentation d’accès ne peut pas encore être affichée ici.',
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
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Il est rechargé depuis Makolo lorsque cette surface revient au premier plan.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
