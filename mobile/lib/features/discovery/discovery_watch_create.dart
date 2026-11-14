import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'discovery_repository.dart';

/// Watch creation is an explicit owner mutation, never a Save side effect.
/// The dialog returns a Watch identity only after server confirmation.
Future<String?> showDiscoveryWatchCreation(
  BuildContext context, {
  required DiscoveryRepository repository,
  required DiscoveryQuery query,
  String? watchId,
  String? initialName,
}) async {
  return showDialog<String>(
    context: context,
    builder: (_) => _CreateDiscoveryWatchDialog(
      repository: repository,
      query: query,
      watchId: watchId,
      initialName: initialName,
    ),
  );
}

class _CreateDiscoveryWatchDialog extends StatefulWidget {
  const _CreateDiscoveryWatchDialog({
    required this.repository,
    required this.query,
    this.watchId,
    this.initialName,
  });

  final DiscoveryRepository repository;
  final DiscoveryQuery query;
  final String? watchId;
  final String? initialName;

  @override
  State<_CreateDiscoveryWatchDialog> createState() =>
      _CreateDiscoveryWatchDialogState();
}

class _CreateDiscoveryWatchDialogState
    extends State<_CreateDiscoveryWatchDialog> {
  late final TextEditingController _name;
  late final TextEditingController _keywords;
  late final TextEditingController _place;
  late final TextEditingController _from;
  late final TextEditingController _to;
  late String _vertical;
  late String _when;
  late String _price;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _keywords = TextEditingController(text: widget.query.text);
    _place = TextEditingController(text: widget.query.place);
    _from = TextEditingController(text: widget.query.dateFrom);
    _to = TextEditingController(text: widget.query.dateTo);
    _vertical = widget.query.vertical;
    _when = widget.query.when;
    _price = widget.query.price;
    final candidate = widget.query.text.trim().isNotEmpty
        ? widget.query.text.trim()
        : widget.query.place.trim().isNotEmpty
        ? 'Veille · ${widget.query.place.trim()}'
        : 'Ma veille';
    _name = TextEditingController(
      text:
          widget.initialName ??
          (candidate.length <= 140 ? candidate : candidate.substring(0, 140)),
    );
  }

  @override
  void dispose() {
    _name.dispose();
    _keywords.dispose();
    _place.dispose();
    _from.dispose();
    _to.dispose();
    super.dispose();
  }

  Future<void> _chooseDate(TextEditingController target) async {
    final initial = DateTime.tryParse(target.text) ?? DateTime.now();
    final selected = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) {
      final month = selected.month.toString().padLeft(2, '0');
      final day = selected.day.toString().padLeft(2, '0');
      setState(() {
        target.text = '${selected.year}-$month-$day';
        _when = '';
      });
    }
  }

  Future<void> _create() async {
    if (_saving) return;
    final name = _name.text.trim();
    if (name.isEmpty || name.length > 140) {
      setState(() => _error = 'Donnez un nom de 1 à 140 caractères.');
      return;
    }
    final query = widget.query.copyWith(
      text: _keywords.text.trim(),
      place: _place.text.trim(),
      dateFrom: _from.text.trim(),
      dateTo: _to.text.trim(),
      vertical: _vertical,
      when: _when,
      price: _price,
      page: 1,
      clearContinuation: true,
    );
    if (query.watchCriteria.isEmpty) {
      setState(() => _error = 'Ajoutez au moins un mot-clé ou un filtre.');
      return;
    }
    if ((_when.isNotEmpty || widget.query.date.isNotEmpty) &&
        (_from.text.trim().isNotEmpty || _to.text.trim().isNotEmpty)) {
      setState(() => _error = 'Choisissez une période ou une plage de dates.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      if (widget.watchId != null) {
        await widget.repository.editWatch(
          widget.watchId!,
          name: name,
          replaceCriteria: query,
        );
        if (mounted) Navigator.of(context).pop(widget.watchId);
      } else {
        final id = await widget.repository.createWatch(
          name: name,
          query: query,
        );
        if (mounted) Navigator.of(context).pop(id);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'Changement non confirmé. Vérifiez la connexion et les critères.',
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
        widget.watchId == null ? 'Nouvelle veille' : 'Modifier la veille',
      ),
      content: SizedBox(
        width: 450,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Définissez les critères de recherche de cette veille.',
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('discover-watch-keywords'),
                controller: _keywords,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Mots-clés',
                  hintText: 'Ex. logistique',
                ),
              ),
              TextField(
                key: const Key('discover-watch-place'),
                controller: _place,
                decoration: const InputDecoration(
                  labelText: 'Lieu',
                  hintText: 'Ex. Lubumbashi',
                ),
              ),
              DropdownButtonFormField<String>(
                initialValue: _vertical,
                decoration: const InputDecoration(labelText: 'Type'),
                items: const [
                  DropdownMenuItem(value: '', child: Text('Tous les types')),
                  DropdownMenuItem(value: 'event', child: Text('Événements')),
                  DropdownMenuItem(
                    value: 'transport',
                    child: Text('Transports'),
                  ),
                  DropdownMenuItem(value: 'service', child: Text('Services')),
                  DropdownMenuItem(
                    value: 'other',
                    child: Text('Autres activités'),
                  ),
                ],
                onChanged: (v) => setState(() => _vertical = v ?? ''),
              ),
              DropdownButtonFormField<String>(
                initialValue: _when,
                decoration: const InputDecoration(labelText: 'Période'),
                items: const [
                  DropdownMenuItem(value: '', child: Text('Toutes dates')),
                  DropdownMenuItem(value: 'today', child: Text('Aujourd’hui')),
                  DropdownMenuItem(value: 'tomorrow', child: Text('Demain')),
                  DropdownMenuItem(value: 'week', child: Text('Cette semaine')),
                  DropdownMenuItem(
                    value: 'weekend',
                    child: Text('Ce week-end'),
                  ),
                ],
                onChanged: (v) => setState(() {
                  _when = v ?? '';
                  if (_when.isNotEmpty) {
                    _from.clear();
                    _to.clear();
                  }
                }),
              ),
              DropdownButtonFormField<String>(
                initialValue: _price,
                decoration: const InputDecoration(labelText: 'Prix'),
                items: const [
                  DropdownMenuItem(value: '', child: Text('Tous les prix')),
                  DropdownMenuItem(value: 'free', child: Text('Gratuit')),
                  DropdownMenuItem(value: 'paid', child: Text('Payant')),
                ],
                onChanged: (v) => setState(() => _price = v ?? ''),
              ),
              const SizedBox(height: 8),
              const Text('Plage de dates (facultative)'),
              TextField(
                key: const Key('discover-watch-from'),
                controller: _from,
                readOnly: true,
                onTap: () => _chooseDate(_from),
                decoration: const InputDecoration(
                  labelText: 'À partir du',
                  hintText: 'Choisir une date',
                  suffixIcon: Icon(Icons.calendar_today_outlined),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('discover-watch-to'),
                controller: _to,
                readOnly: true,
                onTap: () => _chooseDate(_to),
                decoration: const InputDecoration(
                  labelText: 'Jusqu’au',
                  hintText: 'Choisir une date',
                  suffixIcon: Icon(Icons.calendar_today_outlined),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('discover-watch-name'),
                controller: _name,
                maxLength: 140,
                decoration: const InputDecoration(
                  labelText: 'Nom de la veille',
                ),
                onSubmitted: (_) => _create(),
              ),
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        ),
      ),
      actions: [
        MakoloActionButton(
          label: 'Annuler',
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          appearance: MakoloActionAppearance.quiet,
        ),
        MakoloActionButton(
          key: const Key('discover-watch-confirm'),
          label: _saving
              ? 'Enregistrement…'
              : widget.watchId == null
              ? 'Créer la veille'
              : 'Enregistrer',
          onPressed: _saving ? null : _create,
          appearance: MakoloActionAppearance.primary,
          busy: _saving,
        ),
      ],
    );
  }
}
