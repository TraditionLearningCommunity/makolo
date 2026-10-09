import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import '../../repositories/interoperability_repository.dart';
import '../../sync/sync_status.dart';

class ProfileConnectionsScreen extends StatefulWidget {
  const ProfileConnectionsScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<ProfileConnectionsScreen> createState() =>
      _ProfileConnectionsScreenState();
}

class _ProfileConnectionsScreenState extends State<ProfileConnectionsScreen> {
  bool _requestedInitialRefresh = false;

  static const _capabilityLabels = <String, String>{
    'text_generate': 'Génération de texte',
    'structured_generate': 'Données structurées',
    'embed': 'Représentation sémantique',
    'rerank': 'Classement de résultats',
    'web_research': 'Recherche sur le Web',
  };

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    unawaited(_ensureProjection());
  }

  Future<void> _ensureProjection() async {
    final repository = widget.runtime.interoperability;
    final sync = widget.runtime.sync;
    if (repository == null || sync == null) return;
    final current = await repository.read();
    if (current == null) {
      try {
        await sync.pullInteroperability();
      } on Object {
        // Existing cached data is never discarded by a failed refresh.
      }
    }
  }

  String _humanize(String value, {String fallback = 'Service'}) {
    if (value.trim().isEmpty) return fallback;
    final text = value
        .replaceAll('.', ' ')
        .replaceAll('_', ' ')
        .replaceAll('-', ' ')
        .trim()
        .replaceAll(RegExp(r'\s+'), ' ');
    if (text.isEmpty) return fallback;
    return text[0].toUpperCase() + text.substring(1);
  }

  String _capabilityLabel(String value) =>
      _capabilityLabels[value] ?? _humanize(value, fallback: 'Capacité disponible');

  String _connectionState(InteroperabilityConnectionProjection connection) {
    if (!connection.enabled || connection.status == 'disabled') {
      return 'Désactivé';
    }
    if (connection.health == 'unavailable') {
      return 'Momentanément indisponible';
    }
    if (connection.health == 'degraded') {
      return connection.connected
          ? 'Connecté · disponibilité réduite'
          : 'Disponibilité réduite';
    }
    if (connection.health == 'unknown') {
      return connection.connected
          ? 'Connecté · état à vérifier'
          : 'État à vérifier';
    }
    if (connection.connected && connection.usable) {
      return 'Connecté et disponible';
    }
    if (connection.connected) return 'Connecté';
    return connection.available ? 'Disponible' : 'État à vérifier';
  }

  Widget _sectionTitle(BuildContext context, String label) {
    return Padding(
      padding: const EdgeInsets.only(top: MakoloSpacing.lg, bottom: MakoloSpacing.sm),
      child: Text(label, style: Theme.of(context).textTheme.titleMedium),
    );
  }

  Widget _connectionRow(InteroperabilityConnectionProjection connection) {
    final capabilities = connection.capabilities.map(_capabilityLabel).toList();
    return Column(
      children: [
        ListTile(
          key: Key('connection-${connection.id}'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.link_outlined),
          title: Text(connection.displayName),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_connectionState(connection)),
              if (capabilities.isNotEmpty)
                Text(capabilities.join(' · ')),
            ],
          ),
        ),
        const Divider(height: 1),
      ],
    );
  }

  Widget _providerRow(InteroperabilityProviderProjection provider) {
    final capabilities = provider.capabilities.map(_capabilityLabel).toList();
    return Column(
      children: [
        ListTile(
          key: Key('provider-${provider.code}'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.extension_outlined),
          title: const Text('Service disponible'),
          subtitle: Text(
            capabilities.isEmpty ? 'Disponible' : 'Disponible · ${capabilities.join(' · ')}',
          ),
        ),
        const Divider(height: 1),
      ],
    );
  }

  Widget _extensionRow(InteroperabilityExtensionProjection extension) {
    return Column(
      children: [
        ListTile(
          key: Key('extension-${extension.code}'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.widgets_outlined),
          title: Text(_humanize(extension.code, fallback: 'Extension')),
          subtitle: const Text('Disponible'),
        ),
        const Divider(height: 1),
      ],
    );
  }

  Widget _actionRow(InteroperabilityActionProjection action) {
    final status = action.available
        ? 'Disponible'
        : action.requiresConnection
        ? 'Connexion requise'
        : 'Indisponible pour le moment';
    return Column(
      children: [
        ListTile(
          key: Key('action-${action.code}'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.bolt_outlined),
          title: Text(_humanize(action.code, fallback: 'Action')),
          subtitle: Text(status),
          enabled: action.available,
        ),
        const Divider(height: 1),
      ],
    );
  }

  Widget _freshnessNotice(BuildContext context, SyncStatus? syncStatus) {
    if (syncStatus == null) return const SizedBox.shrink();
    if (syncStatus.state == SyncVisualState.syncing) {
      return const LinearProgressIndicator(
        key: Key('profile-connections-refreshing'),
        minHeight: 2,
      );
    }
    if (syncStatus.state == SyncVisualState.offline ||
        syncStatus.state == SyncVisualState.stale ||
        syncStatus.state == SyncVisualState.failed) {
      return Padding(
        key: const Key('profile-connections-last-known'),
        padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
        child: Text(
          'Dernier état connu. La disponibilité actuelle peut avoir changé.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }
    return const SizedBox.shrink();
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
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          _freshnessNotice(context, syncStatus),
          const MakoloEmptyState(
            title: 'Aucune connexion pour le moment',
            body: 'Aucun service n’est encore disponible pour votre Profil.',
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
        Text(
          'Les services externes reliés à votre Profil et ce que Makolo peut réellement utiliser maintenant.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        if (projection.connections.isNotEmpty) ...[
          _sectionTitle(context, 'Mes connexions'),
          for (final connection in projection.connections)
            _connectionRow(connection),
        ],
        if (projection.providers.isNotEmpty) ...[
          _sectionTitle(context, 'Services disponibles'),
          Text(
            'La disponibilité d’un service ne signifie pas qu’un parcours de connexion est fourni ici.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final provider in projection.providers) _providerRow(provider),
        ],
        if (projection.actions.isNotEmpty) ...[
          _sectionTitle(context, 'Capacités et actions'),
          for (final action in projection.actions) _actionRow(action),
        ],
        if (projection.extensions.isNotEmpty) ...[
          _sectionTitle(context, 'Extensions'),
          for (final extension in projection.extensions)
            _extensionRow(extension),
        ],
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
          preservedMessage:
              'Vos autres données Makolo restent disponibles normalement.',
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Connexions')),
      body: StreamBuilder<ProfileInteroperabilityProjection?>(
        stream: repository.watch(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return const MakoloErrorState(
              message: 'Impossible de lire vos connexions pour le moment.',
              preservedMessage:
                  'Aucun secret ni aucune donnée de connexion n’a été modifié.',
            );
          }

          final syncStatus = SyncStatusScope.maybeOf(context);
          final projection = snapshot.data;
          if (projection != null) {
            return _content(context, projection, syncStatus);
          }

          if (syncStatus?.state == SyncVisualState.offline) {
            return ListView(
              key: const Key('profile-connections-offline-empty'),
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(MakoloSpacing.lg),
              children: const [
                MakoloEmptyState(
                  title: 'Connexions indisponibles hors ligne',
                  body:
                      'Aucune copie locale n’est encore disponible. Le reste de Makolo continue de fonctionner.',
                ),
              ],
            );
          }

          return const Center(child: CircularProgressIndicator());
        },
      ),
    );
  }
}
