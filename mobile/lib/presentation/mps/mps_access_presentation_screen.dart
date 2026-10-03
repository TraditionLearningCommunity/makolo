import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import 'mps_models.dart';
import 'mps_native_renderer.dart';
import 'mps_repository.dart';

class MpsAccessPresentationScreen extends StatefulWidget {
  const MpsAccessPresentationScreen({
    super.key,
    required this.accessId,
    required this.repository,
    required this.onOpenCredential,
  });

  final String accessId;
  final MpsPresentationRepository repository;
  final void Function(String credentialPath) onOpenCredential;

  @override
  State<MpsAccessPresentationScreen> createState() =>
      _MpsAccessPresentationScreenState();
}

class _MpsAccessPresentationScreenState
    extends State<MpsAccessPresentationScreen> {
  MpsPresentationPackage? _package;
  Object? _error;
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant MpsAccessPresentationScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.accessId != widget.accessId ||
        oldWidget.repository != widget.repository) {
      _package = null;
      _error = null;
      unawaited(_load());
    }
  }

  Future<void> _load() async {
    final local = await widget.repository.readAccessPackage(widget.accessId);
    if (mounted && local != null) setState(() => _package = local);
    await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() {
      _refreshing = true;
      _error = null;
    });
    try {
      await widget.repository.refreshAccess(widget.accessId);
      final next = await widget.repository.readAccessPackage(widget.accessId);
      if (mounted && next != null) setState(() => _package = next);
    } on Object catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final value = _package;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Présentation'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: switch ((value, _refreshing, _error)) {
        (null, true, _) => const MakoloLoadingState(
          label: 'Chargement de la présentation…',
        ),
        (null, false, _) when _error != null => MakoloErrorState(
          message: 'Cette présentation n’est pas disponible pour le moment.',
          onRetry: _refresh,
        ),
        (final package?, _, _) => Stack(
          children: [
            Positioned.fill(
              child: MpsNativeRenderer(
                package: package,
                onOpenCredential: package.artifact.canOpenCredential
                    ? () => widget.onOpenCredential(
                        package.artifact.links['credential']!,
                      )
                    : null,
              ),
            ),
            if (_refreshing)
              const Positioned(
                left: MakoloSpacing.inner,
                right: MakoloSpacing.inner,
                bottom: MakoloSpacing.inner,
                child: LinearProgressIndicator(),
              ),
          ],
        ),
        _ => const MakoloLoadingState(
          label: 'Chargement de la présentation…',
        ),
      },
    );
  }
}
