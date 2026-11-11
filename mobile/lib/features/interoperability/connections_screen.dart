import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import '../../repositories/interoperability_repository.dart';
import '../../sync/sync_status.dart';
import 'intelligence_connection_controls.dart';

class ProfileConnectionsScreen extends StatefulWidget {
  const ProfileConnectionsScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<ProfileConnectionsScreen> createState() =>
      _ProfileConnectionsScreenState();
}

class _ProfileConnectionsScreenState extends State<ProfileConnectionsScreen> {
  bool _requestedInitialRefresh = false;
  bool _initialLoadComplete = false;
  bool _refreshing = false;
  bool _refreshFailed = false;
  int _ownerGeneration = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    unawaited(_ensureProjection());
  }

  @override
  void didUpdateWidget(covariant ProfileConnectionsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.runtime, widget.runtime)) {
      _ownerGeneration++;
      _requestedInitialRefresh = true;
      _initialLoadComplete = false;
      _refreshFailed = false;
      _refreshing = false;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_ensureProjection());
      });
    }
  }

  Future<void> _ensureProjection() async {
    final generation = _ownerGeneration;
    try {
      // Cached Z16 is an observation, not current permission to mutate.
      // Refresh even when a snapshot exists; a failure preserves it.
      if (widget.runtime.sync != null) {
        await _refresh();
      }
    } on Object {
      if (mounted && generation == _ownerGeneration) {
        setState(() => _refreshFailed = true);
      }
    } finally {
      if (mounted && generation == _ownerGeneration) {
        setState(() => _initialLoadComplete = true);
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing || !mounted) return;
    final generation = _ownerGeneration;
    final sync = widget.runtime.sync;
    if (sync == null) {
      setState(() => _refreshFailed = true);
      return;
    }
    setState(() {
      _refreshing = true;
      _refreshFailed = false;
    });
    try {
      // Z16 remains server-owned. Do not change the cached projection until
      // the owner response has been validated and applied by SyncEngine.
      await sync.pullInteroperability();
    } on Object {
      if (mounted && generation == _ownerGeneration) {
        setState(() => _refreshFailed = true);
      }
    } finally {
      if (mounted && generation == _ownerGeneration) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _refreshAndConfirm() async {
    if (_refreshing) throw StateError('Vérification déjà en cours.');
    final generation = _ownerGeneration;
    final repository = widget.runtime.interoperability;
    if (repository == null) {
      throw StateError('Impossible de vérifier les connexions.');
    }
    final before = await repository.read();
    await _refresh();
    if (generation != _ownerGeneration || _refreshFailed || _refreshing) {
      throw StateError('Impossible de confirmer les connexions.');
    }
    // A discarded/out-of-order SyncEngine pull resolves without throwing.
    // A real server-applied projection must have a newer observation timestamp.
    final after = await repository.read();
    if (after == null ||
        (before != null && !after.receivedAt.isAfter(before.receivedAt))) {
      throw StateError('Actualisation non confirmée.');
    }
  }

  Widget _freshnessNotice(BuildContext context, SyncStatus? syncStatus) {
    if (_refreshing || syncStatus?.state == SyncVisualState.syncing) {
      return const LinearProgressIndicator(
        key: Key('profile-connections-refreshing'),
        minHeight: 2,
      );
    }
    // The shell already shows degraded connectivity. Keep mutation gates
    // intact; do not repeat a local-cache explanation over known entries.
    return const SizedBox.shrink();
  }

  bool _mutationsAllowed(SyncStatus? status) {
    if (!_initialLoadComplete ||
        _refreshing ||
        _refreshFailed ||
        !widget.runtime.isAuthenticated ||
        widget.runtime.api == null ||
        widget.runtime.sync == null) {
      return false;
    }
    return status?.state != SyncVisualState.offline &&
        status?.state != SyncVisualState.failed &&
        status?.state != SyncVisualState.stale &&
        status?.state != SyncVisualState.conflict &&
        status?.state != SyncVisualState.syncing;
  }

  Widget _content(
    BuildContext context,
    ProfileInteroperabilityProjection projection,
    SyncStatus? syncStatus,
  ) {
    return ListView(
      key: const Key('profile-connections-list'),
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.lg,
        MakoloSpacing.md,
        MakoloSpacing.lg,
        MakoloSpacing.strong,
      ),
      children: [
        _freshnessNotice(context, syncStatus),
        IntelligenceConnectionControls(
          runtime: widget.runtime,
          path: 'api/v1/me/intelligence/connections/',
          connections: projection.connections,
          onChanged: _refreshAndConfirm,
          mutationsEnabled: _mutationsAllowed(syncStatus),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final repository = widget.runtime.interoperability;
    if (repository == null) {
      return const Scaffold(
        body: MakoloErrorState(
          message: 'Vos connexions ne sont pas disponibles sur cet appareil.',
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Connexions'),
        actions: [
          if (widget.runtime.sync != null)
            IconButton(
              tooltip: 'Actualiser les connexions',
              onPressed: _refreshing ? null : () => unawaited(_refresh()),
              icon: const Icon(Icons.refresh),
            ),
        ],
      ),
      body: StreamBuilder<ProfileInteroperabilityProjection?>(
        stream: repository.watch(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return MakoloErrorState(
              message: 'Impossible d’afficher vos connexions.',
              preservedMessage:
                  'Aucun secret ni aucune donnée de connexion n’a été modifié.',
              onRetry: widget.runtime.sync == null
                  ? null
                  : () => unawaited(_refresh()),
            );
          }

          final syncStatus = SyncStatusScope.maybeOf(context);
          final projection = snapshot.data;
          if (projection != null) {
            return RefreshIndicator(
              onRefresh: _refresh,
              child: _content(context, projection, syncStatus),
            );
          }

          if (syncStatus?.state == SyncVisualState.offline) {
            return ListView(
              key: const Key('profile-connections-offline-empty'),
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                SizedBox(
                  height: 520,
                  child: MakoloEmptyState(
                    title: 'Aucune connexion disponible.',
                  ),
                ),
              ],
            );
          }

          if (_initialLoadComplete && !_refreshing) {
            return MakoloErrorState(
              message: 'Impossible de vérifier vos connexions.',
              preservedMessage: 'Aucune connexion n’a été modifiée. Réessayez lorsque le serveur est joignable.',
              onRetry: widget.runtime.sync == null
                  ? null
                  : () => unawaited(_refresh()),
            );
          }

          return const MakoloLoadingState(
            label: 'Vérification des connexions…',
          );
        },
      ),
    );
  }
}
