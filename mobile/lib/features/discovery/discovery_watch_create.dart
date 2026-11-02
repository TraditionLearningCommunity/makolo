import 'package:flutter/material.dart';

import 'discovery_repository.dart';

/// Watch creation is an explicit owner mutation, never a Save side effect.
/// The dialog returns a Watch identity only after server confirmation.
Future<String?> showDiscoveryWatchCreation(
  BuildContext context, {
  required DiscoveryRepository repository,
  required DiscoveryQuery query,
}) async {
  if (query.watchCriteria.isEmpty) return null;
  return showDialog<String>(
    context: context,
    builder: (_) => _CreateDiscoveryWatchDialog(
      repository: repository,
      query: query,
    ),
  );
}

class _CreateDiscoveryWatchDialog extends StatefulWidget {
  const _CreateDiscoveryWatchDialog({
    required this.repository,
    required this.query,
  });

  final DiscoveryRepository repository;
  final DiscoveryQuery query;

  @override
  State<_CreateDiscoveryWatchDialog> createState() =>
      _CreateDiscoveryWatchDialogState();
}

class _CreateDiscoveryWatchDialogState extends State<_CreateDiscoveryWatchDialog> {
  late final TextEditingController _name;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final candidate = widget.query.text.trim().isNotEmpty
        ? widget.query.text.trim()
        : widget.query.place.trim().isNotEmpty
            ? 'Veille · ${widget.query.place.trim()}'
            : 'Ma veille';
    _name = TextEditingController(
      text: candidate.length <= 140 ? candidate : candidate.substring(0, 140),
    );
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    if (_saving) return;
    final name = _name.text.trim();
    if (name.isEmpty || name.length > 140) {
      setState(() => _error = 'Donnez un nom de 1 à 140 caractères.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final id = await widget.repository.createWatch(
        name: name,
        query: widget.query,
      );
      if (mounted) Navigator.of(context).pop(id);
    } on Object {
      if (mounted) {
        setState(() => _error =
            'Veille non confirmée. Vérifiez les critères et réessayez.');
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Créer une veille'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Cette veille réutilise les filtres de votre recherche. '
              'Elle n’enregistre ni une possibilité ni une participation.'),
          const SizedBox(height: 16),
          TextField(
            key: const Key('discover-watch-name'),
            controller: _name,
            maxLength: 140,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Nom de la veille'),
            onSubmitted: (_) => _create(),
          ),
          if (_error != null)
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Annuler'),
        ),
        FilledButton(
          key: const Key('discover-watch-confirm'),
          onPressed: _saving ? null : _create,
          child: _saving
              ? const SizedBox(width: 18, height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Créer la veille'),
        ),
      ],
    );
  }
}
