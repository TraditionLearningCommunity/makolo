import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../sync/owner_source_state.dart';
import 'space_repository.dart';

/// Secondary Space surfaces. Owner snapshots stay in WorkspaceContextRepository.
/// Presentation never grants authority and never mutates a relationship or metric.
class SpaceInsightScreen extends StatefulWidget {
  const SpaceInsightScreen({
    super.key,
    required this.runtime,
    required this.surface,
  });

  final AppRuntime runtime;
  final SpaceProjectionKind surface;

  @override
  State<SpaceInsightScreen> createState() => _SpaceInsightScreenState();
}

class _SpaceInsightScreenState extends State<SpaceInsightScreen> {
  final _query = TextEditingController();
  Map<String, dynamic>? _remoteSearch;
  bool _searchUnavailable = false;
  bool _refreshing = false;
  String? _selectedKind;
  String? _selectedId;
  int _searchVersion = 0;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onContextChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onContextChanged);
    _query.dispose();
    super.dispose();
  }

  void _onContextChanged() {
    if (!mounted) return;
    setState(() {
      _remoteSearch = null;
      _selectedKind = null;
      _selectedId = null;
      _searchUnavailable = false;
      _searchVersion++;
    });
    _refresh();
  }

  SpaceActorContext? get _actor {
    final current = widget.runtime.actorContext?.value;
    return current is SpaceActorContext ? current : null;
  }

  WorkspaceContextRepository? get _repository => widget.runtime.space;

  Future<void> _refresh() async {
    final actor = _actor;
    final repo = _repository;
    if (actor == null || repo == null || _refreshing) return;
    setState(() => _refreshing = true);
    try {
      if (widget.surface == SpaceProjectionKind.relationships) {
        await repo.refreshRelationships(actor.space);
      } else {
        await repo.refreshPilot(actor.space);
      }
    } on Object {
      // Keep only the authorized last snapshot; the source state signals
      // revocation, and live search never misreports a remote failure.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _search() async {
    final actor = _actor;
    final api = widget.runtime.api;
    final query = _query.text.trim();
    final version = ++_searchVersion;
    if (actor == null || query.isEmpty) {
      setState(() {
        _remoteSearch = null;
        _searchUnavailable = false;
      });
      return;
    }
    if (api == null) {
      setState(() {
        _remoteSearch = null;
        _searchUnavailable = true;
      });
      return;
    }
    try {
      final url = 'api/v1/organizations/workspaces/'
          '${Uri.encodeComponent(actor.space.slug)}/relationships/'
          '?q=${Uri.encodeQueryComponent(query)}';
      final response = await api.get(url);
      if (!mounted || version != _searchVersion || _actor?.space.id != actor.space.id) return;
      final payload = response.jsonObject();
      setState(() {
        _remoteSearch = payload['search'] is Map
            ? Map<String, dynamic>.from(payload['search'] as Map)
            : null;
        _searchUnavailable = false;
      });
    } on Object {
      if (!mounted || version != _searchVersion) return;
      setState(() {
        _remoteSearch = null;
        _searchUnavailable = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    final repo = _repository;
    final title = widget.surface == SpaceProjectionKind.relationships
        ? 'Personnes & relations'
        : 'Piloter';
    if (actor == null || repo == null) {
      return Scaffold(
        appBar: AppBar(title: Text(title)),
        body: const Center(child: Text('Cette surface exige le contexte Space actif.')),
      );
    }
    final source = widget.surface == SpaceProjectionKind.relationships
        ? repo.relationshipsSource(actor.space)
        : repo.pilotSource(actor.space);
    final stream = widget.surface == SpaceProjectionKind.relationships
        ? repo.watchRelationships(actor.space)
        : repo.watchPilot(actor.space);
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: StreamBuilder<OwnerSourceState>(
        stream: repo.watchSource(source),
        initialData: OwnerSourceState.unknown,
        builder: (context, stateSnapshot) {
          final state = stateSnapshot.data ?? OwnerSourceState.unknown;
          if (state.invalidated || state.lastErrorCode == 'forbidden' ||
              state.lastErrorCode == 'not_found') {
            return const Center(
              child: Text('Cette profondeur n’est plus autorisée dans le contexte Space actuel.'),
            );
          }
          return StreamBuilder<StoredProjection?>(
            key: ValueKey('${actor.space.id}:${widget.surface.name}'),
            stream: stream,
            builder: (context, snapshot) {
              final payload = snapshot.data?.payload;
              if (payload == null) {
                return const Center(child: Text('Aucune projection autorisée disponible.'));
              }
              if (widget.surface == SpaceProjectionKind.relationships) {
                return _relations(context, payload);
              }
              return _pilot(context, payload);
            },
          );
        },
      ),
    );
  }

  Widget _relations(BuildContext context, Map<String, dynamic> payload) {
    final authority = payload['authority'] is Map ? payload['authority'] as Map : const {};
    final sections = payload['sections'] is Map ? payload['sections'] as Map : const {};
    final label = payload['label'] is String ? payload['label'] as String : 'Personnes & relations';
    const families = {
      'team': 'Équipe',
      'groups': 'Groupes',
      'crm_contacts': 'Contacts',
      'audiences': 'Audiences',
      'partners': 'Partenaires',
    };
    final local = <Map<String, dynamic>>[];
    for (final entry in families.entries) {
      final collection = sections[entry.key];
      if (collection is! Map || collection['items'] is! List) continue;
      for (final raw in collection['items'] as List) {
        if (raw is Map) local.add(Map<String, dynamic>.from(raw));
      }
    }
    final query = _query.text.trim().toLowerCase();
    final search = _remoteSearch;
    final remoteMatches = search?['items'] is List ? search!['items'] as List : null;
    final displayed = query.isEmpty
        ? local
        : remoteMatches != null
            ? remoteMatches.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList()
            : local.where((row) => _name(row).toLowerCase().contains(query)).toList();
    return ListView(
      key: const Key('space-relationships-secondary'),
      padding: const EdgeInsets.all(20),
      children: [
        Text(label, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        const Text('Avec qui avançons-nous ?'),
        const SizedBox(height: 16),
        TextField(
          controller: _query,
          onChanged: (_) => setState(() {
            _remoteSearch = null;
            _searchVersion++;
          }),
          onSubmitted: (_) => _search(),
          decoration: InputDecoration(
            labelText: 'Rechercher les relations visibles',
            suffixIcon: IconButton(
              tooltip: 'Rechercher dans le Space',
              onPressed: _search,
              icon: const Icon(Icons.search),
            ),
          ),
        ),
        if (_searchUnavailable && query.isNotEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('Résultats disponibles sur cet appareil. La recherche complète du Space est indisponible.'),
          ),
        if (authority['scope'] == 'activity_limited')
          const Padding(
            padding: EdgeInsets.only(top: 16),
            child: Text('Relations globales indisponibles dans cette responsabilité.'),
          )
        else if (sections.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 16),
            child: Text('Aucune collection relationnelle disponible dans ce contexte.'),
          )
        else if (query.isNotEmpty) ...[
          if (displayed.isEmpty)
            Text(search == null
                ? 'Aucune relation correspondante dans le snapshot disponible sur cet appareil.'
                : 'Aucune relation visible ne correspond à cette recherche.'),
          for (final row in displayed) _relationTile(row),
          if (search?['has_more'] == true)
            const Text('Des résultats supplémentaires peuvent exister. Affinez la recherche.'),
        ] else
          for (final family in families.entries)
            if (sections[family.key] is Map) ...[
              const SizedBox(height: 20),
              Text(family.value, style: Theme.of(context).textTheme.titleMedium),
              for (final raw in ((sections[family.key] as Map)['items'] as List? ?? const []))
                if (raw is Map) _relationTile(Map<String, dynamic>.from(raw)),
              if ((sections[family.key] as Map)['has_more'] == true)
                const Text('Voir toutes les relations dans le domaine propriétaire.'),
            ],
        if (_selectedKind != null && _selectedId != null)
          const Padding(
            padding: EdgeInsets.only(top: 20),
            child: Text('Sélection locale : ouvrir la relation dans son owner après revalidation serveur.'),
          ),
      ],
    );
  }

  Widget _relationTile(Map<String, dynamic> row) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(_name(row)),
      subtitle: Text(row['relation_type']?.toString() ?? _type(row['kind']?.toString() ?? '')),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => setState(() {
        _selectedKind = row['kind']?.toString();
        _selectedId = row['id']?.toString();
      }),
    );
  }

  String _name(Map row) {
    if (row['identity'] is String) return row['identity'] as String;
    final profile = row['profile'];
    if (profile is Map && profile['name'] is String) return profile['name'] as String;
    return row['name']?.toString() ?? row['label']?.toString() ?? 'Relation';
  }

  String _type(String kind) => switch (kind) {
    'team_member' => 'Collaborateur · Équipe',
    'crm_contact' => 'Contact CRM',
    'group' => 'Groupe',
    'audience' => 'Audience',
    'partner' => 'Partenaire',
    _ => 'Relation propriétaire',
  };

  Widget _pilot(BuildContext context, Map<String, dynamic> payload) {
    final authority = payload['authority'] is Map ? payload['authority'] as Map : const {};
    final sections = payload['sections'] is Map ? payload['sections'] as Map : const {};
    final analytics = sections['analytics'] is Map ? sections['analytics'] as Map : null;
    final signals = payload['signals'] is List ? payload['signals'] as List : const [];
    return ListView(
      key: const Key('space-pilot-secondary'),
      padding: const EdgeInsets.all(20),
      children: [
        Text('Piloter', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        const Text('Est-ce que cela fonctionne ? Qu’est-ce qui change ? Que devons-nous ajuster ?'),
        const SizedBox(height: 20),
        if (authority['scope'] == 'activity_limited')
          const Text('Le pilotage global n’est pas disponible dans cette responsabilité.')
        else if (analytics == null)
          const Text('Aucune lecture de pilotage disponible avec cette autorité.')
        else ...[
          if (signals.isEmpty)
            Text(analytics['state'] == 'insufficient_data'
                ? 'Pas encore assez d’activité pour dégager une tendance utile.'
                : 'Aucun signal de pilotage défendable disponible pour le moment.'),
          for (final raw in signals)
            if (raw is Map)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(raw['title']?.toString() ?? 'Observation', style: Theme.of(context).textTheme.titleLarge),
                      if (raw['summary'] != null) Text(raw['summary'].toString()),
                      if (raw['why'] != null) Text(raw['why'].toString()),
                      if (raw['uncertainty'] != null) Text('Limite : ${raw['uncertainty']}'),
                      Text('Source : ${raw['owner'] ?? 'Owner analytique'}'),
                    ],
                  ),
                ),
              ),
          const SizedBox(height: 20),
          ExpansionTile(
            title: const Text('Mesures de soutien'),
            subtitle: Text('Portefeuille : ${(analytics['coverage'] is Map ? (analytics['coverage'] as Map)['limit'] : null) ?? 'portée non précisée'} événements visibles maximum'),
            children: [
              for (final metric in analytics['metrics'] is List ? analytics['metrics'] as List : const [])
                if (metric is Map)
                  ListTile(
                    title: Text(metric['key']?.toString() ?? 'Mesure'),
                    subtitle: Text(_metricText(metric)),
                  ),
              for (final money in analytics['money'] is List ? analytics['money'] as List : const [])
                if (money is Map)
                  ListTile(
                    title: Text('Finance · ${money['currency']}'),
                    subtitle: Text('Brut ${money['gross']} · Remboursements ${money['refunds']} · Net ${money['net']}'),
                  ),
            ],
          ),
        ],
      ],
    );
  }

  String _metricText(Map metric) => switch (metric['state']) {
    'known' => '${metric['value']} ${metric['unit'] ?? ''}',
    'unknown' => 'Inconnu',
    'unavailable' => 'Indisponible',
    'insufficient_data' => 'Données insuffisantes',
    _ => 'État non disponible',
  };
}
