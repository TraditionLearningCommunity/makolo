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
        // The screen will render the shared offline/error state. Existing
        // cached data is never discarded by a failed refresh.
      }
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

  String _connectionState(InteroperabilityConnectionProjection connection) {
    if (!connection.enabled || connection.status == 'disabled') {
      return 'Désactivé';
    }
    if (connection.health == 'unavailable') {
      return 'Indisponible pour le moment';
    }
    if (connection.usable) return 'Connecté et disponible';
    if (connection.connected) return 'Connecté';
    return connection.available ? 'Disponible' : 'Indisponible';
  }

  Widget _connectionCard(InteroperabilityConnectionProjection connection) {
    return Card(
      child: ListTile(
        key: Key('connection-${connection.id}'),
        leading: const Icon(Icons.link_outlined),
        title: Text(connection.displayName),
        subtitle: Text(_connectionState(connection)),
      ),
    );
  }

  Widget _providerCard(InteroperabilityProviderProjection provider) {
    return Card(
      child: ListTile(
        key: Key('provider-${provider.code}'),
        leading: const Icon(Icons.extension_outlined),
        title: Text(_humanize(provider.code)),
        subtitle: Text(provider.available ? 'Disponible' : 'Indisponible'),
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
              ? 'Action disponible'
              : action.requiresConnection
              ? 'Connexion requise'
              : 'Indisponible pour le moment',
        ),
        enabled: available,
      ),
    );
  }

  Widget _content(
    BuildContext context,
    ProfileInteroperabilityProjection projection,
  ) {
    if (projection.isEmpty) {
      return ListView(
        key: const Key('profile-connections-empty'),
        physics: const AlwaysScrollableScrollPhysics(),
        children: const [
          SizedBox(
            height: 520,
            child: MakoloEmptyState(
              title: 'Aucune connexion pour le moment',
              body:
                  'Aucun service ni aucune extension n’est encore disponible pour votre Profil.',
            ),
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
        MakoloSpacing.xxl,
      ),
      children: [
        Text(
          'Reliez Makolo aux services que vous utilisez.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        if (projection.connections.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text('Mes connexions', style: Theme.of(context).textTheme.titleMedium),
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
          for (final provider in projection.providers)
            _providerCard(provider),
        ],
        if (projection.actions.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text(
            'Actions disponibles',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final action in projection.actions)
            _actionCard(action),
        ],
        const SizedBox(height: MakoloSpacing.lg),
        Text('Extensions', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: MakoloSpacing.sm),
        if (projection.extensions.isEmpty)
          Text(
            'Aucune extension disponible pour le moment.',
            style: Theme.of(context).textTheme.bodyMedium,
          )
        else
          for (final extension in projection.extensions)
            _extensionCard(extension),
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

          final projection = snapshot.data;
          if (projection != null) {
            return _content(context, projection);
          }

          final syncStatus = SyncStatusScope.maybeOf(context);
          if (syncStatus?.state == SyncVisualState.offline) {
            return ListView(
              key: const Key('profile-connections-offline-empty'),
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                SizedBox(
                  height: 520,
                  child: MakoloEmptyState(
                    title: 'Connexions indisponibles hors ligne',
                    body:
                        'Aucune copie locale n’est encore disponible. Réessayez lorsque le réseau revient.',
                  ),
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
