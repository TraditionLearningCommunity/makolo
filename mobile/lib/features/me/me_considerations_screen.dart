import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/projection_contract.dart';

/// Explicit personal choices, not recommendations inferred from browsing.
class MeConsiderationsScreen extends StatefulWidget {
  const MeConsiderationsScreen({
    super.key, required this.api, required this.personal,
    required this.onSaved, required this.onWatches,
  });
  final MakoloApiClient api;
  final PersonalRepository personal;
  final VoidCallback onSaved;
  final VoidCallback onWatches;

  @override
  State<MeConsiderationsScreen> createState() => _MeConsiderationsState();
}

class _MeConsiderationsState extends State<MeConsiderationsScreen> {
  bool _loading = true, _saving = false;
  String? _error;
  List<Map<String, dynamic>> _topics = [], _openOptions = [];
  Set<String> _interests = {}, _openTo = {};

  @override
  void initState() { super.initState(); _load(); }

  static List<Map<String, dynamic>> _options(Object? raw) =>
      raw is List ? raw.whereType<Map>().map((m) =>
        m.map((key, value) => MapEntry(key.toString(), value))).toList()
        : const [];

  Future<void> _load() async {
    try {
      final response = await widget.api.get('api/v1/me/considerations/settings/');
      final data = ProjectionEnvelope.parse(
        response.jsonObject(), expectedProjection: 'personal.me.settings',
      ).data;
      if (!mounted) return;
      setState(() {
        _topics = _options(data['topics']);
        _openOptions = _options(data['open_to_options']);
        _interests = (data['interests'] as List? ?? []).map((v) => '$v').toSet();
        _openTo = (data['open_to'] as List? ?? []).map((v) => '$v').toSet();
        _loading = false; _error = null;
      });
    } on Object {
      if (mounted) setState(() {
        _loading = false; _error = 'Impossible de charger vos préférences.';
      });
    }
  }

  Future<void> _save(String family, Set<String> values) async {
    if (_saving) return;
    setState(() { _saving = true; _error = null; });
    try {
      final result = await widget.api.put(
        'api/v1/me/considerations/settings/',
        body: {'family': family, 'values': values.toList()},
      );
      final data = ProjectionEnvelope.parse(
        result.jsonObject(), expectedProjection: 'personal.me.settings',
      ).data;
      if (!mounted) return;
      setState(() {
        _interests = (data['interests'] as List? ?? []).map((v) => '$v').toSet();
        _openTo = (data['open_to'] as List? ?? []).map((v) => '$v').toSet();
        _saving = false;
      });
      // Owner confirmed the change: update the only local personal projection.
      try {
        final root = await widget.api.get('api/v1/me/');
        final envelope = ProjectionEnvelope.parse(
          root.jsonObject(), expectedProjection: 'personal.me',
        );
        if (envelope.data['actor'] is Map &&
            (envelope.data['actor'] as Map)['id']?.toString() ==
                widget.personal.store.profileId) {
          await widget.personal.store.putProjection(
            kind: 'personal.me', schemaVersion: envelope.schemaVersion,
            payload: envelope.data, receivedAt: DateTime.now().toUtc(),
            sourceGeneratedAt: envelope.generatedAt,
          );
        }
      } on Object {
        // Saved on the server; local source will reconcile on next refresh.
      }
    } on Object {
      if (mounted) setState(() {
        _saving = false; _error = 'Modification non enregistrée. Réessayez.';
      });
    }
  }

  Widget _choices(String title, List<Map<String, dynamic>> options,
      Set<String> selected, String family) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(0, 18, 0, 10),
        child: Text(title, style: Theme.of(context).textTheme.titleLarge),
      ),
      Wrap(spacing: 8, runSpacing: 6, children: [
        for (final option in options)
          if (option['id'] != null && option['label'] != null)
            FilterChip(
              label: Text(option['label'].toString()),
              selected: selected.contains(option['id'].toString()),
              onSelected: _saving ? null : (active) {
                final next = Set<String>.from(selected);
                final key = option['id'].toString();
                if (active) { next.add(key); } else { next.remove(key); }
                _save(family, next);
              },
            ),
      ]),
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Ce qui compte pour moi')),
    body: _loading
        ? const Center(child: CircularProgressIndicator.adaptive())
        : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              TextButton(onPressed: _load, child: const Text('Réessayer')),
            ],
            _choices('Mes intérêts', _topics, _interests, 'interests'),
            _choices('Ouvert à', _openOptions, _openTo, 'open_to'),
            const SizedBox(height: 20),
            const Divider(),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.notifications_active_outlined),
              title: const Text('Mes veilles'),
              trailing: const Icon(Icons.chevron_right),
              onTap: widget.onWatches,
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.bookmark_added_outlined),
              title: const Text('Mes enregistrés'),
              trailing: const Icon(Icons.chevron_right),
              onTap: widget.onSaved,
            ),
          ]),
  );
}
