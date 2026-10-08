import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../sync/owner_source_state.dart';
import 'space_repository.dart';

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
  final searchController = TextEditingController();
  Map<String, dynamic>? results;
  bool searchFailed = false;
  int searchVersion = 0;

  SpaceActorContext? get actor {
    final current = widget.runtime.actorContext?.value;
    return current is SpaceActorContext ? current : null;
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => refresh());
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(onActorChanged);
    searchController.dispose();
    super.dispose();
  }

  void onActorChanged() {
    if (!mounted) return;
    searchVersion++;
    setState(() {
      results = null;
      searchFailed = false;
    });
    unawaited(refresh());
  }

  Future<void> refresh() async {
    final space = actor?.space;
    final repository = widget.runtime.space;
    if (space == null || repository == null) return;
    try {
      if (widget.surface == SpaceProjectionKind.relationships) {
        await repository.refreshRelationships(space);
      } else {
        await repository.refreshPilot(space);
      }
    } on Object {
      // The source state decides whether cached data remains usable.
    }
  }

  Future<void> search() async {
    final space = actor?.space;
    final api = widget.runtime.api;
    final query = searchController.text.trim();
    final version = ++searchVersion;
    if (space == null || api == null || query.isEmpty) {
      setState(() {
        results = null;
        searchFailed = query.isNotEmpty;
      });
      return;
    }
    try {
      final path =
          'api/v1/organizations/workspaces/'
          '${Uri.encodeComponent(space.slug)}/relationships/'
          '?q=${Uri.encodeQueryComponent(query)}';
      final response = await api.get(path);
      if (!mounted || version != searchVersion) return;
      if (actor?.space.id != space.id) return;
      final payload = response.jsonObject();
      setState(() {
        results = payload['search'] is Map
            ? Map<String, dynamic>.from(payload['search'] as Map)
            : null;
        searchFailed = false;
      });
    } on Object {
      if (!mounted || version != searchVersion) return;
      setState(() {
        results = null;
        searchFailed = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final space = actor?.space;
    final repository = widget.runtime.space;
    final relations = widget.surface == SpaceProjectionKind.relationships;
    final title = relations ? 'Personnes & relations' : 'Piloter';
    if (space == null || repository == null) {
      return Scaffold(
        appBar: AppBar(title: Text(title)),
        body: const Center(child: Text('Contexte Space indisponible.')),
      );
    }
    final source = relations
        ? repository.relationshipsSource(space)
        : repository.pilotSource(space);
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: StreamBuilder<OwnerSourceState>(
        stream: repository.watchSource(source),
        initialData: OwnerSourceState.unknown,
        builder: (context, sourceSnapshot) {
          final status = sourceSnapshot.data;
          if (status?.invalidated == true) {
            return const Center(
              child: Text('Autorité Space révoquée ou indisponible.'),
            );
          }
          return StreamBuilder<StoredProjection?>(
            key: ValueKey('${space.id}:${widget.surface.name}'),
            stream: relations
                ? repository.watchRelationships(space)
                : repository.watchPilot(space),
            builder: (context, snapshot) {
              final payload = snapshot.data?.payload;
              if (payload == null) {
                return const Center(child: Text('Projection non disponible.'));
              }
              return relations ? relationsBody(payload) : pilotBody(payload);
            },
          );
        },
      ),
    );
  }

  Widget relationsBody(Map<String, dynamic> payload) {
    final sections = payload['sections'];
    if (sections is! Map || sections.isEmpty) {
      return const Center(
        child: Text('Aucune relation visible dans ce contexte.'),
      );
    }
    final query = searchController.text.trim();
    final matches = results?['items'];
    final rows = <Map<String, dynamic>>[];
    if (query.isNotEmpty && matches is List) {
      for (final item in matches) {
        if (item is Map) rows.add(Map<String, dynamic>.from(item));
      }
    } else {
      for (final section in sections.values) {
        if (section is! Map || section['items'] is! List) continue;
        for (final item in section['items'] as List) {
          if (item is Map) {
            final row = Map<String, dynamic>.from(item);
            if (query.isEmpty ||
                labelOf(row).toLowerCase().contains(query.toLowerCase())) {
              rows.add(row);
            }
          }
        }
      }
    }
    return ListView(
      key: const Key('space-relationships-secondary'),
      padding: const EdgeInsets.all(20),
      children: [
        const Text('Relations conservées dans leurs domaines propriétaires.'),
        const SizedBox(height: 12),
        TextField(
          controller: searchController,
          onChanged: (_) {
            searchVersion++;
            setState(() => results = null);
          },
          onSubmitted: (_) => search(),
          decoration: InputDecoration(
            labelText: 'Rechercher les relations',
            suffixIcon: IconButton(
              tooltip: 'Rechercher dans le Space',
              onPressed: search,
              icon: const Icon(Icons.search),
            ),
          ),
        ),
        if (searchFailed)
          const Text(
            'Recherche distante indisponible. Résultats locaux partiels.',
          ),
        if (rows.isEmpty)
          const Text(
            'Aucune relation correspondante dans les données visibles.',
          ),
        for (final row in rows)
          ListTile(
            title: Text(labelOf(row)),
            subtitle: Text(row['relation_type']?.toString() ?? 'Relation'),
          ),
        if (results?['has_more'] == true)
          const Text('Autres résultats possibles : affinez la recherche.'),
      ],
    );
  }

  String labelOf(Map<String, dynamic> row) {
    final profile = row['profile'];
    if (row['identity'] is String) return row['identity'] as String;
    if (profile is Map && profile['name'] is String) {
      return profile['name'] as String;
    }
    return row['name']?.toString() ?? row['label']?.toString() ?? 'Relation';
  }

  Widget pilotBody(Map<String, dynamic> payload) {
    final sections = payload['sections'];
    final analytics = sections is Map ? sections['analytics'] : null;
    if (analytics is! Map) {
      return const Center(
        child: Text('Pilotage non autorisé ou indisponible.'),
      );
    }
    final signals = analytics['signals'] is List
        ? analytics['signals'] as List
        : const [];
    final metrics = analytics['metrics'] is List
        ? analytics['metrics'] as List
        : const [];
    return ListView(
      key: const Key('space-pilot-secondary'),
      padding: const EdgeInsets.all(20),
      children: [
        Text('Piloter', style: Theme.of(context).textTheme.headlineSmall),
        const Text('Que savons-nous ? Que faut-il examiner ?'),
        const SizedBox(height: 20),
        if (signals.isEmpty)
          const Text('Aucun signal interprétable à ce stade.'),
        for (final signal in signals)
          if (signal is Map)
            ListTile(
              title: Text(signal['title']?.toString() ?? 'Observation'),
              subtitle: Text(signal['summary']?.toString() ?? ''),
            ),
        const SizedBox(height: 12),
        ExpansionTile(
          title: const Text('Mesures de soutien'),
          children: [
            for (final metric in metrics)
              if (metric is Map)
                ListTile(
                  title: Text(metric['key']?.toString() ?? 'Mesure'),
                  subtitle: Text(
                    metric['state'] == 'known'
                        ? '${metric['value']}'
                        : metric['state']?.toString() ?? 'Inconnu',
                  ),
                ),
          ],
        ),
      ],
    );
  }
}
