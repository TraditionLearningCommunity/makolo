import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../repositories/interoperability_repository.dart';

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

  @override
  void initState() {
    super.initState();
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
      unawaited(_loadCatalog());
    }
  }

  bool _scopeUnchanged(String path, AppRuntime runtime) =>
      mounted && widget.path == path &&
      identical(widget.runtime, runtime);

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
      if (!mounted || generation != _catalogGeneration ||
          path != widget.path || !identical(runtime, widget.runtime)) return;
      if (offers is! List) throw const FormatException('Invalid owner catalog');
      setState(() {
        _offers = offers.whereType<Map<String, dynamic>>()
            .toList(growable: false);
        _catalogLoading = false;
        _catalogError = null;
      });
    } on Object {
      if (!mounted || generation != _catalogGeneration ||
          path != widget.path || !identical(runtime, widget.runtime)) return;
      setState(() {
        _offers = const [];
        _catalogLoading = false;
        _catalogError = 'Catalogue indisponible. Vérifiez votre connexion ou vos droits.';
      });
    }
  }

  void _notice(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _submit({
    String? id,
    required String method,
    required Map<String, dynamic> body,
  }) async {
    if (_busy || !widget.mutationsEnabled || widget.runtime.api == null) return;
    final ownerPath = widget.path;
    final ownerRuntime = widget.runtime;
    final mutationVersion = ++_mutationGeneration;
    setState(() => _busy = true);
    var committed = false;
    try {
      final api = ownerRuntime.api!;
      final path = id == null ? ownerPath : '${ownerPath}$id/';
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
        mutationVersion != _mutationGeneration) return;
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
  }

  Future<void> _create(Map<String, dynamic> offer) async {
    final ownerPath = widget.path;
    final ownerRuntime = widget.runtime;
    final name = TextEditingController(text: offer['label'] as String? ?? '');
    final model = TextEditingController();
    final secret = TextEditingController();
    final accepted = ValueNotifier<bool>(false);
    try {
      final proceed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text('Relier ${offer['label']}'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(offer['description'] as String? ?? ''),
                const SizedBox(height: 12),
                const Text(
                  'Votre clé reste chiffrée sur le serveur Makolo. '
                  'Les appels peuvent être facturés par le fournisseur.',
                ),
                ValueListenableBuilder<bool>(
                  valueListenable: accepted,
                  builder: (context, value, _) => CheckboxListTile(
                    value: value,
                    onChanged: (next) => accepted.value = next == true,
                    title: const Text(
                      'J’autorise Makolo à utiliser cette clé '
                      'pour les capacités indiquées.',
                    ),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                ),
                TextField(
                  controller: name,
                  decoration: const InputDecoration(
                    labelText: 'Nom de la connexion',
                  ),
                  maxLength: 120,
                ),
                if (offer['requires_model'] == true)
                  TextField(
                    controller: model,
                    decoration: const InputDecoration(
                      labelText: 'Identifiant du modèle',
                    ),
                    maxLength: 160,
                  ),
                TextField(
                  controller: secret,
                  obscureText: true,
                  enableSuggestions: false,
                  autocorrect: false,
                  decoration: const InputDecoration(labelText: 'Clé API'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(accepted.value),
              child: const Text('Relier'),
            ),
          ],
        ),
      );
      if (proceed != true || !_sameOwner(ownerPath, ownerRuntime)) return;
      if (name.text.trim().isEmpty ||
          secret.text.trim().isEmpty ||
          (offer['requires_model'] == true && model.text.trim().isEmpty)) {
        _notice('Renseignez le nom, la clé et le modèle si nécessaire.');
        return;
      }
      await _submit(
        method: 'POST',
        body: {
          'provider': offer['code'],
          'name': name.text.trim(),
          'model': model.text.trim(),
          'api_key': secret.text.trim(),
          'consent': true,
        },
      );
    } finally {
      name.dispose();
      model.dispose();
      secret.dispose();
      accepted.dispose();
    }
  }

  Future<void> _manage(
    InteroperabilityConnectionProjection connection,
    String action,
  ) async {
    if (_busy || !widget.mutationsEnabled) return;
    final ownerPath = widget.path;
    final ownerRuntime = widget.runtime;
    if (action == 'rotate') {
      final controller = TextEditingController();
      try {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text('Remplacer la clé API'),
            content: TextField(
              controller: controller,
              obscureText: true,
              enableSuggestions: false,
              autocorrect: false,
              decoration: const InputDecoration(labelText: 'Nouvelle clé API'),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(false),
                child: const Text('Annuler'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(dialogContext).pop(true),
                child: const Text('Remplacer'),
              ),
            ],
          ),
        );
        if (confirmed == true && controller.text.trim().isNotEmpty &&
            _sameOwner(ownerPath, ownerRuntime)) {
          await _submit(
            id: connection.id,
            method: 'PATCH',
            body: {'api_key': controller.text.trim()},
          );
        }
      } finally {
        controller.dispose();
      }
      return;
    }
    if (action == 'disconnect') {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Retirer cette connexion ?'),
          content: const Text(
            'Les credentials conservés par Makolo seront '
            'supprimés. Votre clé externe reste sous le contrôle du fournisseur.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Retirer'),
            ),
          ],
        ),
      );
      if (confirmed == true && _sameOwner(ownerPath, ownerRuntime)) {
        await _submit(id: connection.id, method: 'DELETE', body: const {});
      }
      return;
    }
    if (!_sameOwner(ownerPath, ownerRuntime)) return;
    await _submit(
      id: connection.id,
      method: 'PATCH',
      body: {'enabled': action == 'enable'},
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.runtime.api == null) return const SizedBox.shrink();
    final connectable = _offers
        .where((row) => row['can_connect'] == true)
        .toList();
    final manageable = widget.connections
        .where((row) => row.manageable && row.owner == 'intelligence')
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (_catalogLoading) const LinearProgressIndicator(minHeight: 2),
        if (_catalogError != null)
          TextButton.icon(
            onPressed: () => unawaited(_loadCatalog()),
            icon: const Icon(Icons.refresh),
            label: Text(_catalogError!),
          ),
        if (!widget.mutationsEnabled)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text(
              'Actions de connexion suspendues hors ligne ou tant '
              'que les droits ne sont pas confirmés. Réessayez une fois connecté.',
            ),
          ),
        if (connectable.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(
            'Relier un service Intelligence',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const Text(
            'Utilisez une clé API qui vous appartient. '
            'Il ne s’agit pas d’un accès à votre compte social.',
          ),
          for (final offer in connectable)
            ListTile(
              leading: const Icon(Icons.add_link),
              title: Text(offer['label'] as String? ?? 'Service'),
              subtitle: Text(offer['description'] as String? ?? ''),
              enabled: !_busy && widget.mutationsEnabled,
              onTap: () => unawaited(_create(offer)),
            ),
        ],
        if (_offers.isNotEmpty && connectable.isEmpty)
          const Text(
            'La configuration sécurisée des connexions '
            'est indisponible sur ce serveur.',
          ),
        if (manageable.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text(
            'Gérer les connexions',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          for (final connection in manageable)
            ListTile(
              title: Text(connection.displayName),
              trailing: PopupMenuButton<String>(
                enabled: !_busy && widget.mutationsEnabled,
                tooltip: 'Gérer la connexion',
                onSelected: (action) => unawaited(_manage(connection, action)),
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: connection.enabled ? 'disable' : 'enable',
                    child: Text(
                      connection.enabled ? 'Désactiver' : 'Réactiver',
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'rotate',
                    child: Text('Remplacer la clé'),
                  ),
                  const PopupMenuItem(
                    value: 'disconnect',
                    child: Text('Retirer de Makolo'),
                  ),
                ],
              ),
            ),
        ],
      ],
    );
  }
}
