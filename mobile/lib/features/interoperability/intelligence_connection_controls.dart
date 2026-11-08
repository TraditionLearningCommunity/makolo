import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../repositories/interoperability_repository.dart';
import 'connection_detail_screen.dart';
import 'interoperability_presentation.dart';

/// Owner-specific credential controls. Secrets are never written to ProfileStore
/// and provider endpoints are never supplied by the client.
class IntelligenceConnectionControls extends StatefulWidget {
  const IntelligenceConnectionControls({
    super.key,
    required this.runtime,
    required this.path,
    required this.connections,
    required this.onChanged,
    this.mutationsEnabled = true,
  });

  final AppRuntime runtime;
  final String path;
  final List<InteroperabilityConnectionProjection> connections;
  final Future<void> Function() onChanged;
  final bool mutationsEnabled;

  @override
  State<IntelligenceConnectionControls> createState() =>
      _IntelligenceConnectionControlsState();
}

class _IntelligenceConnectionControlsState
    extends State<IntelligenceConnectionControls> {
  List<Map<String, dynamic>> _offers = const [];
  bool _busy = false;
  bool _catalogLoading = true;
  int _catalogGeneration = 0;
  int _mutationGeneration = 0;
  String? _catalogError;
  String _view = 'discover';
  String _query = '';
  String _capabilityFilter = '';

  @override
  void initState() {
    super.initState();
    if (widget.runtime.api == null && widget.connections.isNotEmpty) {
      _view = 'manage';
    }
    unawaited(_loadCatalog());
  }

  @override
  void didUpdateWidget(covariant IntelligenceConnectionControls oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path ||
        !identical(oldWidget.runtime, widget.runtime)) {
      // New actor/scope: never carry a provider offer from another owner.
      _catalogGeneration++;
      _mutationGeneration++;
      _busy = false;
      _offers = const [];
      _catalogLoading = true;
      _catalogError = null;
      _view = 'discover';
      _query = '';
      _capabilityFilter = '';
      unawaited(_loadCatalog());
    }
  }

  bool _scopeUnchanged(String path, AppRuntime runtime) =>
      mounted && widget.path == path && identical(widget.runtime, runtime);

  bool _sameOwner(String path, AppRuntime runtime) =>
      _scopeUnchanged(path, runtime) && widget.mutationsEnabled;

  Future<void> _loadCatalog() async {
    final generation = ++_catalogGeneration;
    final path = widget.path;
    final runtime = widget.runtime;
    final api = runtime.api;
    if (api == null) {
      if (mounted && generation == _catalogGeneration) {
        setState(() {
          _offers = const [];
          _catalogLoading = false;
          _catalogError = 'Service Connexions indisponible.';
        });
      }
      return;
    }
    try {
      final result = (await api.get(path)).jsonObject();
      final offers = result['offers'];
      if (!mounted ||
          generation != _catalogGeneration ||
          path != widget.path ||
          !identical(runtime, widget.runtime)) {
        return;
      }
      if (offers is! List) throw const FormatException('Invalid owner catalog');
      setState(() {
        _offers = offers.whereType<Map<String, dynamic>>().toList(
          growable: false,
        );
        _catalogLoading = false;
        _catalogError = null;
      });
    } on Object {
      if (!mounted ||
          generation != _catalogGeneration ||
          path != widget.path ||
          !identical(runtime, widget.runtime)) {
        return;
      }
      setState(() {
        _offers = const [];
        _catalogLoading = false;
        _catalogError =
            'Catalogue indisponible. Vérifiez votre connexion ou vos droits.';
      });
    }
  }

  void _notice(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<bool> _submit({
    String? id,
    required String method,
    required Map<String, dynamic> body,
  }) async {
    if (_busy || !widget.mutationsEnabled || widget.runtime.api == null) {
      return false;
    }
    final ownerPath = widget.path;
    final ownerRuntime = widget.runtime;
    final mutationVersion = ++_mutationGeneration;
    setState(() => _busy = true);
    var committed = false;
    try {
      final api = ownerRuntime.api!;
      final path = id == null ? ownerPath : '$ownerPath$id/';
      if (method == 'POST') {
        await api.post(path, body: body);
      } else if (method == 'PATCH') {
        await api.patch(path, body: body);
      } else {
        await api.delete(path);
      }
      committed = true;
    } on Object {
      // Server failure or unknown result: never write optimistic local state.
    }

    var refreshed = false;
    try {
      if (_scopeUnchanged(ownerPath, ownerRuntime)) {
        await widget.onChanged();
        refreshed = true;
      }
    } on Object {
      // Server commit and local projection refresh are separate outcomes.
    }
    if (!_scopeUnchanged(ownerPath, ownerRuntime) ||
        mutationVersion != _mutationGeneration) {
      return false;
    }
    if (!committed) {
      _notice(
        'Opération non confirmée par le serveur. Vérifiez votre autorité.',
      );
    } else if (!refreshed) {
      _notice(
        'Modification enregistrée sur le serveur, mais '
        'l’actualisation de cet écran est indisponible.',
      );
    } else {
      _notice(
        method == 'DELETE'
            ? 'Connexion retirée de Makolo. Révoquez aussi la clé chez le fournisseur.'
            : 'Connexion enregistrée sur le serveur.',
      );
    }
    if (mounted && mutationVersion == _mutationGeneration) {
      setState(() => _busy = false);
    }
    return committed;
  }

  Future<void> _openOffer(Map<String, dynamic> offer) async {
    final ownerPath = widget.path;
    final ownerRuntime = widget.runtime;
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ConnectionDetailScreen.offer(
          offer: offer,
          mutationsEnabled: widget.mutationsEnabled,
          onConnect: (fields) async {
            if (!_sameOwner(ownerPath, ownerRuntime)) return false;
            return _submit(
              method: 'POST',
              body: {
                'provider': offer['code'],
                'name': fields['name'],
                'model': fields['model'],
                'api_key': fields['api_key'],
                'consent': true,
              },
            );
          },
        ),
      ),
    );
  }

  Future<void> _openConnection(
    InteroperabilityConnectionProjection connection,
  ) async {
    final ownerPath = widget.path;
    final ownerRuntime = widget.runtime;
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ConnectionDetailScreen.connected(
          connection: connection,
          mutationsEnabled: widget.mutationsEnabled,
          onManage: (action, secret) async {
            if (!_sameOwner(ownerPath, ownerRuntime)) return false;
            if (action == 'rotate') {
              if (secret == null || secret.trim().isEmpty) return false;
              return _submit(
                id: connection.id,
                method: 'PATCH',
                body: {'api_key': secret.trim()},
              );
            }
            if (action == 'disconnect') {
              return _submit(
                id: connection.id,
                method: 'DELETE',
                body: const {},
              );
            }
            return _submit(
              id: connection.id,
              method: 'PATCH',
              body: {'enabled': action == 'enable'},
            );
          },
        ),
      ),
    );
  }

  Widget _serviceIcon(BuildContext context, {required bool connected}) {
    return Container(
      width: 48,
      height: 48,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Icon(
        connected ? Icons.link_outlined : Icons.extension_outlined,
        color: Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    );
  }

  Widget _offerRow(BuildContext context, Map<String, dynamic> offer) {
    final title = offer['label'] as String? ?? 'Service';
    final description = offer['description'] as String? ?? '';
    final enabled = offer['can_connect'] == true;
    return ListTile(
      key: Key('connection-offer-${offer['code']}'),
      contentPadding: const EdgeInsets.symmetric(vertical: 6),
      minVerticalPadding: 10,
      leading: _serviceIcon(context, connected: false),
      title: Text(
        title,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.titleMedium,
      ),
      subtitle: Text(
        description.isEmpty
            ? (enabled ? 'Service connectable' : 'Non connectable actuellement')
            : description,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => unawaited(_openOffer(offer)),
    );
  }

  Widget _connectionRow(
    BuildContext context,
    InteroperabilityConnectionProjection connection,
  ) {
    return ListTile(
      key: Key('manage-connection-${connection.id}'),
      contentPadding: const EdgeInsets.symmetric(vertical: 6),
      minVerticalPadding: 10,
      leading: _serviceIcon(context, connected: true),
      title: Text(
        connection.displayName,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.titleMedium,
      ),
      subtitle: Text(
        connectionStatusLabel(connection),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => unawaited(_openConnection(connection)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final connections = widget.connections;
    final availableCapabilities = <String>{
      for (final offer in _offers)
        ...((offer['capabilities'] as List?)?.whereType<String>() ??
            <String>[]),
    }.toList()..sort();
    final query = _query.trim().toLowerCase();
    final visibleOffers = _offers
        .where((offer) {
          final capabilities =
              (offer['capabilities'] as List?)?.whereType<String>() ??
              <String>[];
          if (_capabilityFilter.isNotEmpty &&
              !capabilities.contains(_capabilityFilter)) {
            return false;
          }
          return [
            offer['label'] as String? ?? '',
            offer['description'] as String? ?? '',
            ...capabilities,
          ].join(' ').toLowerCase().contains(query);
        })
        .toList(growable: false);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 20),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            ChoiceChip(
              label: const Text('Découvrir'),
              selected: _view == 'discover',
              showCheckmark: false,
              onSelected: (_) => setState(() => _view = 'discover'),
            ),
            ChoiceChip(
              label: const Text('Mes connexions'),
              selected: _view == 'manage',
              showCheckmark: false,
              onSelected: (_) => setState(() => _view = 'manage'),
            ),
          ],
        ),
        const SizedBox(height: 24),
        if (_view == 'discover') ...[
          Row(
            children: [
              Expanded(
                child: Text(
                  'Services à découvrir',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton(
                tooltip: 'Actualiser les services',
                onPressed: _catalogLoading
                    ? null
                    : () => unawaited(_loadCatalog()),
                icon: const Icon(Icons.refresh_outlined),
              ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('connection-catalog-search'),
            onChanged: (value) => setState(() => _query = value),
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: 'Rechercher un service',
              border: OutlineInputBorder(),
            ),
          ),
          if (availableCapabilities.isNotEmpty) ...[
            const SizedBox(height: 12),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  ChoiceChip(
                    label: const Text('Tous'),
                    selected: _capabilityFilter.isEmpty,
                    onSelected: (_) => setState(() => _capabilityFilter = ''),
                  ),
                  for (final capability in availableCapabilities) ...[
                    const SizedBox(width: 8),
                    ChoiceChip(
                      label: Text(connectionCapabilityLabel(capability)),
                      selected: _capabilityFilter == capability,
                      onSelected: (_) =>
                          setState(() => _capabilityFilter = capability),
                    ),
                  ],
                ],
              ),
            ),
          ],
          if (_catalogLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: LinearProgressIndicator(minHeight: 2),
            ),
          if (_catalogError != null)
            TextButton.icon(
              onPressed: () => unawaited(_loadCatalog()),
              icon: const Icon(Icons.refresh),
              label: Text(_catalogError!),
            ),
          if (!_catalogLoading &&
              _catalogError == null &&
              visibleOffers.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Text('Aucun service ne correspond à votre recherche.'),
            ),
          for (var index = 0; index < visibleOffers.length; index++) ...[
            _offerRow(context, visibleOffers[index]),
            if (index < visibleOffers.length - 1) const Divider(height: 1),
          ],
          if (_offers.isNotEmpty && !widget.mutationsEnabled)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(
                'Vous pouvez explorer les services. '
                'Toute connexion nécessite une vérification du serveur.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ] else ...[
          Text(
            'Mes services connectés',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          if (connections.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Text(
                'Aucune connexion établie. Découvrez un service pour commencer.',
              ),
            ),
          for (var index = 0; index < connections.length; index++) ...[
            _connectionRow(context, connections[index]),
            if (index < connections.length - 1) const Divider(height: 1),
          ],
          if (connections.isNotEmpty && !widget.mutationsEnabled)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(
                'Dernier état connu. La gestion sera disponible après vérification.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ],
    );
  }
}
