import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import '../../repositories/interoperability_repository.dart';
import '../../sync/sync_status.dart';
import 'intelligence_connection_controls.dart';
import 'interoperability_presentation.dart';
import 'push_device_controls.dart';

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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    unawaited(_ensureProjection());
  }

  Future<void> _ensureProjection() async {
    try {
      final current = await widget.runtime.interoperability?.read();
      if (current == null && mounted) {
        await _refresh();
      }
    } on Object {
      if (mounted) setState(() => _refreshFailed = true);
    } finally {
      if (mounted) setState(() => _initialLoadComplete = true);
    }
  }

  Future<void> _refresh() async {
    if (_refreshing || !mounted) return;
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
      if (mounted) setState(() => _refreshFailed = true);
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  String _humanize(String value) {
    if (value.trim().isEmpty) return 'Service';
    final text = value
        .replaceAll('.', ' ')
        .replaceAll('_', ' ')
        .replaceAll('-', ' ')
        .trim();
    if (text.isEmpty) return 'Service';
    return text[0].toUpperCase() + text.substring(1);
  }

  String _capabilityLabel(String value) => connectionCapabilityLabel(value);

  String _connectionState(InteroperabilityConnectionProjection row) =>
      connectionStatusLabel(row);

  String _experienceExplanation(InteroperabilityConnectionProjection row) =>
      connectionExperienceMessage(row);

  Widget _connectionCard(InteroperabilityConnectionProjection connection) {
    final capabilities = connection.capabilities
        .map(_capabilityLabel)
        .join(' · ');
    return Card(
      child: ListTile(
        key: Key('connection-${connection.id}'),
        leading: const Icon(Icons.link_outlined),
        title: Text(connection.displayName),
        subtitle: Text(
          [
            _connectionState(connection),
            _experienceExplanation(connection),
            if (capabilities.isNotEmpty) capabilities,
          ].join('\n'),
        ),
        isThreeLine: true,
      ),
    );
  }

  Widget _providerCard(InteroperabilityProviderProjection provider) {
    final capabilities = provider.capabilities
        .map(_capabilityLabel)
        .join(' · ');
    return Card(
      child: ListTile(
        key: Key('provider-${provider.code}'),
        leading: const Icon(Icons.extension_outlined),
        title: const Text('Service disponible'),
        subtitle: Text(
          capabilities.isEmpty ? 'Disponible' : 'Disponible · $capabilities',
        ),
      ),
    );
  }

  Widget _extensionCard(InteroperabilityExtensionProjection extension) {
    return Card(
      child: ListTile(
        key: Key('extension-${extension.code}'),
        leading: const Icon(Icons.widgets_outlined),
        title: Text(_humanize(extension.code)),
        subtitle: const Text('Extension disponible pour votre Profil'),
      ),
    );
  }

  Widget _actionCard(InteroperabilityActionProjection action) {
    final available = action.available;
    return Card(
      child: ListTile(
        key: Key('action-${action.code}'),
        leading: const Icon(Icons.bolt_outlined),
        title: Text(_humanize(action.code)),
        subtitle: Text(
          available
              ? 'Disponible'
              : action.requiresConnection
              ? 'Connexion requise'
              : 'Indisponible pour le moment',
        ),
      ),
    );
  }

  Widget _domainIntegrationCard(DomainIntegrationProjection item) {
    final status = item.status == 'sandbox_only'
        ? 'Simulation uniquement, aucun prestataire externe connecté.'
        : item.status == 'manual_available'
        ? 'Traitement manuel selon les droits financiers du contexte.'
        : item.available
        ? '${item.activeCount} appareil(s) enregistré(s).'
        : 'Appareils enregistrés, transport push indisponible.';
    return Card(
      child: ListTile(
        key: Key('domain-integration-${item.code}'),
        leading: Icon(item.kind == 'device_registration'
            ? Icons.notifications_outlined : Icons.account_balance_outlined),
        title: Text(item.displayName),
        subtitle: Text('$status\n${item.description}'),
        isThreeLine: true,
      ),
    );
  }

  Widget _freshnessNotice(BuildContext context, SyncStatus? syncStatus) {
    if (_refreshing || syncStatus?.state == SyncVisualState.syncing) {
      return const LinearProgressIndicator(
        key: Key('profile-connections-refreshing'),
        minHeight: 2,
      );
    }
    if (_refreshFailed ||
        syncStatus?.state == SyncVisualState.offline ||
        syncStatus?.state == SyncVisualState.stale ||
        syncStatus?.state == SyncVisualState.failed) {
      return Padding(
        key: const Key('profile-connections-last-known'),
        padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
        child: Text(
          _refreshFailed
              ? 'Actualisation impossible. Le dernier état connu est conservé.'
              : 'Dernier état connu. La disponibilité actuelle peut avoir changé.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }
    return const SizedBox.shrink();
  }

  bool _mutationsAllowed(SyncStatus? status) {
    if (_refreshFailed || widget.runtime.sync == null) return false;
    return status?.state != SyncVisualState.offline &&
        status?.state != SyncVisualState.failed &&
        status?.state != SyncVisualState.stale &&
        status?.state != SyncVisualState.conflict;
  }

  Widget _content(
    BuildContext context,
    ProfileInteroperabilityProjection projection,
    SyncStatus? syncStatus,
  ) {
    if (projection.isEmpty) {
      return ListView(
        key: const Key('profile-connections-empty'),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          _freshnessNotice(context, syncStatus),
          SizedBox(
            height: widget.runtime.api == null ? 520 : 270,
            child: const MakoloEmptyState(
              title: 'Aucune connexion',
              body: 'Aucun service n’est encore disponible pour votre Profil.',
            ),
          ),
          IntelligenceConnectionControls(
            runtime: widget.runtime,
            path: 'api/v1/me/intelligence/connections/',
            connections: projection.connections,
            onChanged: _refresh,
            mutationsEnabled: _mutationsAllowed(syncStatus),
          ),
        ],
      );
    }

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
        if (projection.connections.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text(
            'Mes connexions',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final connection in projection.connections)
            _connectionCard(connection),
        ],
        if (projection.providers.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text(
            'Services disponibles',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final provider in projection.providers) _providerCard(provider),
        ],
        if (projection.actions.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text(
            'Actions disponibles',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final action in projection.actions) _actionCard(action),
        ],
        if (projection.extensions.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text('Extensions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: MakoloSpacing.sm),
          for (final extension in projection.extensions)
            _extensionCard(extension),
        ],
        if (projection.domainIntegrations.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text('Services utilisés dans Makolo',
              style: Theme.of(context).textTheme.titleMedium),
          for (final integration in projection.domainIntegrations)
            _domainIntegrationCard(integration),
          if (projection.domainIntegrations.any(
              (item) => item.code == 'notifications.push'))
            PushDeviceControls(
              runtime: widget.runtime,
              mutationsEnabled: _mutationsAllowed(syncStatus),
              onChanged: _refresh,
            ),
        ],
        IntelligenceConnectionControls(
          runtime: widget.runtime,
          path: 'api/v1/me/intelligence/connections/',
          connections: projection.connections,
          onChanged: _refresh,
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
                    title: 'Connexions indisponibles hors ligne',
                    body: 'Aucune connexion enregistrée sur cet appareil.',
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
