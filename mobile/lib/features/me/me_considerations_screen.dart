import 'dart:async';

import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../presentation/possibilities/discovery_save_icon.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/projection_contract.dart';
import 'me_local_preview.dart';

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
  bool _loading = true, _saving = false, _searching = false;
  final _query = TextEditingController();
  Timer? _debounce;
  String _activeQuery = '';
  int _requestEpoch = 0;
  String? _error;
  bool _hasKnownChoices = false;
  bool _showingLocal = false;
  int? _interestCount;
  int? _openCount;
  List<Map<String, dynamic>> _topics = [], _openOptions = [], _selectedTopics = [];
  Set<String> _interests = {}, _openTo = {};

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    // The personal.me snapshot is already synced and scoped by ProfileStore.
    // It can restore explicit choices, but not the whole server topic catalog.
    try {
      final snapshot = await widget.personal.store.readProjection('personal.me');
      final local = MeLocalPreview.forProfile(
        snapshot, widget.personal.store.profileId,
      );
      final topics = local?.collection('considerations', 'interests');
      final openness = local?.collection('considerations', 'open_to');
      if (mounted && topics != null && openness != null) {
        final selected = (topics?['items'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .where((row) => row['id'] != null && row['label'] != null)
            .toList();
        final openRows = (openness?['items'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .where((row) => row['id'] != null && row['label'] != null)
            .toList();
        setState(() {
          _selectedTopics = selected;
          _interestCount = topics['count'] is int ? topics['count'] as int : selected.length;
          _openCount = openness['count'] is int ? openness['count'] as int : openRows.length;
          _interests = {for (final row in selected) row['id'].toString()};
          _openOptions = openRows;
          _openTo = {for (final row in openRows) row['id'].toString()};
          _hasKnownChoices = true;
          _showingLocal = true;
          _loading = false;
        });
      }
    } on Object {
      // Missing/corrupt local data must never prevent the online request.
    }
    if (mounted) await _load();
  }

  static List<Map<String, dynamic>> _options(Object? raw) =>
      raw is List ? raw.whereType<Map>().map((m) =>
        m.map((key, value) => MapEntry(key.toString(), value))).toList()
        : const [];

  Future<void> _load() async {
    final query = _query.text.trim();
    _activeQuery = query;
    final epoch = ++_requestEpoch;
    if (_topics.isNotEmpty) setState(() => _searching = true);
    try {
      final uri = Uri(path: 'api/v1/me/considerations/settings/',
        queryParameters: query.isEmpty ? null : {'q': query});
      final response = await widget.api.get(uri.toString());
      if (!mounted || _activeQuery != query || epoch != _requestEpoch) return;
      final data = ProjectionEnvelope.parse(
        response.jsonObject(), expectedProjection: 'personal.me.settings',
      ).data;
      if (!mounted) return;
      setState(() {
        _topics = _options(data['topics']);
        _openOptions = _options(data['open_to_options']);
        _interests = (data['interests'] as List? ?? []).map((v) => '$v').toSet();
        _selectedTopics = _options(data['selected_topics']);
        _openTo = (data['open_to'] as List? ?? []).map((v) => '$v').toSet();
        _loading = false; _searching = false; _error = null;
        _hasKnownChoices = true; _showingLocal = false;
        _interestCount = _interests.length;
        _openCount = _openTo.length;
      });
    } on Object {
      if (mounted && epoch == _requestEpoch) {
        setState(() {
        _loading = false; _searching = false;
        _error = _hasKnownChoices
            ? 'Actualisation impossible. Derniers choix connus affichés.'
            : 'Préférences non disponibles sur cet appareil.';
        _showingLocal = _hasKnownChoices;
        });
      }
    }
  }

  void _onSearch(String text) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 320), _load);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  Future<void> _save(String family, Set<String> values) async {
    if (_saving) return;
    // Invalidate any outstanding search result before applying server-confirmed state.
    ++_requestEpoch;
    setState(() { _saving = true; _searching = false; _error = null; });
    try {
      final result = await widget.api.put(
        'api/v1/me/considerations/settings/',
        body: {'family': family, 'values': values.toList()},
      );
      final confirmed = ProjectionEnvelope.parse(
        result.jsonObject(), expectedProjection: 'personal.me.settings',
      );
      final data = confirmed.data;
      if (!mounted) return;
      setState(() {
        _interests = (data['interests'] as List? ?? []).map((v) => '$v').toSet();
        _selectedTopics = _options(data['selected_topics']);
        _openTo = (data['open_to'] as List? ?? []).map((v) => '$v').toSet();
        _saving = false;
        _hasKnownChoices = true;
        _showingLocal = false;
        _interestCount = _interests.length;
        _openCount = _openTo.length;
      });
      // Only owner-confirmed choices can be reflected into the existing local
      // personal read model. A cache failure never reverses a server success.
      try {
        await widget.personal.reflectMeConfirmedChoices(
          settings: data, confirmedAt: confirmed.generatedAt,
        );
      } on Object {
        // The owner mutation succeeded; normal root sync will reconcile.
      }
      // Refresh the active search after the mutation without allowing an old
      // response to restore stale choices.
      if (_query.text.trim().isNotEmpty) await _load();
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
      if (mounted) {
        setState(() {
          _saving = false; _error = 'Modification non enregistrée. Réessayez.';
        });
      }
    }
  }

  Widget _choices(String title, List<Map<String, dynamic>> options,
      Set<String> selected, String family, {int? knownCount}) {
    final chosen = (family == 'interests' ? _selectedTopics : options)
        .where((item) => selected.contains(item['id']?.toString()))
        .toList();
    final available = options.where((item) =>
        item['id'] != null && item['label'] != null &&
        !selected.contains(item['id'].toString())).toList();
    final colors = Theme.of(context).colorScheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(0, 20, 0, 12),
        child: Text(title, style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800)),
      ),
      Row(children: [
        Icon(Icons.check_circle_outline_rounded, size: 18, color: colors.primary),
        const SizedBox(width: 7),
        Text('Mes choix', style: Theme.of(context).textTheme.titleSmall
            ?.copyWith(fontWeight: FontWeight.w700)),
        const Spacer(),
        Text('${knownCount ?? chosen.length}', style: Theme.of(context).textTheme.labelMedium
            ?.copyWith(color: colors.onSurfaceVariant)),
      ]),
      const SizedBox(height: 10),
      if (chosen.isEmpty)
        Text(_showingLocal && (knownCount ?? 0) > 0
            ? 'Autres choix à actualiser avec une connexion.'
            : 'Aucun choix pour le moment.',
          style: Theme.of(context).textTheme.bodySmall)
      else
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final option in chosen)
            if (option['id'] != null && option['label'] != null)
              InputChip(
                backgroundColor: colors.primaryContainer.withValues(alpha: 0.48),
                side: BorderSide(color: colors.primary.withValues(alpha: 0.14)),
                label: Text(option['label'].toString()),
                onDeleted: _saving ? null : () {
                  final next = Set<String>.from(selected)
                    ..remove(option['id'].toString());
                  _save(family, next);
                },
                deleteIcon: const Icon(Icons.close_rounded, size: 17),
                deleteButtonTooltipMessage: 'Retirer ${option['label']}',
              ),
        ]),
      const SizedBox(height: 20),
      Row(children: [
        Icon(Icons.add_circle_outline_rounded, size: 18,
            color: colors.onSurfaceVariant),
        const SizedBox(width: 7),
        Text('À ajouter', style: Theme.of(context).textTheme.titleSmall
            ?.copyWith(fontWeight: FontWeight.w700)),
      ]),
      const SizedBox(height: 10),
      if (available.isEmpty)
        Text(_showingLocal
            ? 'Suggestions à actualiser avec une connexion.'
            : 'Aucune autre proposition ici.',
          style: Theme.of(context).textTheme.bodySmall)
      else
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final option in available)
            ActionChip(
              avatar: Icon(Icons.add_rounded, size: 17, color: colors.primary),
              label: Text(option['label'].toString()),
              onPressed: _saving ? null : () {
                final next = Set<String>.from(selected)
                  ..add(option['id'].toString());
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
            TextField(
              controller: _query,
              onChanged: _onSearch,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search_rounded),
                hintText: 'Rechercher un intérêt',
                border: OutlineInputBorder(),
              ),
            ),
            if (_searching) const LinearProgressIndicator(minHeight: 2),
            if (_hasKnownChoices) ...[
              _choices('Mes intérêts', _topics, _interests, 'interests',
                knownCount: _interestCount),
              _choices('Ouvert à', _openOptions, _openTo, 'open_to',
                knownCount: _openCount),
            ] else
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  'Vos choix ne sont pas encore disponibles sur cet appareil.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
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
              leading: DiscoveryOrbitIcon(saved: true,
                color: Theme.of(context).colorScheme.primary),
              title: const Text('Mes enregistrements'),
              trailing: const Icon(Icons.chevron_right),
              onTap: widget.onSaved,
            ),
          ]),
  );
}
