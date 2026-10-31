import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/surface_states.dart';
import '../../presentation/contracts/space_presentation.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'space_insight_surfaces.dart';
import 'space_repository.dart';

class SpaceInsightScreen extends StatefulWidget {
  const SpaceInsightScreen({
    super.key,
    required this.runtime,
    required this.surface,
    this.expectedSlug,
  });

  final AppRuntime runtime;
  final SpaceProjectionKind surface;
  final String? expectedSlug;

  @override
  State<SpaceInsightScreen> createState() => _SpaceInsightScreenState();
}

class _SpaceInsightScreenState extends State<SpaceInsightScreen> {
  final searchController = TextEditingController();
  Map<String, dynamic>? results;
  bool searchFailed = false;
  int searchVersion = 0;
  bool refreshing = false;

  SpaceActorContext? get actor {
    final current = widget.runtime.actorContext?.value;
    return current is SpaceActorContext &&
            (widget.expectedSlug == null ||
             current.space.slug == widget.expectedSlug)
        ? current : null;
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

  @override
  void didUpdateWidget(covariant SpaceInsightScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(onActorChanged);
      widget.runtime.actorContext?.addListener(onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.surface != widget.surface ||
      oldWidget.expectedSlug != widget.expectedSlug) {
      searchVersion++;
      results = null;
      searchFailed = false;
      searchController.clear();
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(refresh());
      });
    }
  }

  void onActorChanged() {
    if (!mounted) return;
    searchVersion++;
    setState(() {
      results = null;
      searchFailed = false;
      searchController.clear();
    });
    unawaited(refresh());
  }

  Future<void> refresh() async {
    final space = actor?.space;
    final repository = widget.runtime.space;
    if (space == null || repository == null) return;
    final expectedId = space.id;
    setState(() => refreshing = true);
    try {
      if (widget.surface == SpaceProjectionKind.relationships) {
        await repository.refreshRelationships(space);
      } else {
        await repository.refreshPilot(space);
      }
    } on Object {
      // The source state decides whether cached data remains usable.
    } finally {
      if (mounted && actor?.space.id == expectedId) {
        setState(() => refreshing = false);
      }
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
        key: ValueKey('${space.id}:${widget.surface.name}'),
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
                return refreshing
                    ? const Center(child: CircularProgressIndicator())
                    : MakoloErrorState(
                        message: 'Projection non disponible.',
                        onRetry: refresh,
                      );
              }
              final freshness = WorkspaceContextRepository.surfaceFreshness
                  .evaluate(snapshot.data!, now: DateTime.now());
              if (freshness == FreshnessState.expired) {
                return MakoloErrorState(
                  message: 'Cette observation a expiré.',
                  onRetry: refresh,
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (refreshing) const LinearProgressIndicator(),
                  MakoloFreshnessNotice(
                    freshness: const ProjectionSurfaceAdapter().freshnessCue(
                      freshness,
                    ),
                  ),
                  if (status?.lastErrorCode != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Actualisation indisponible. Observation conservée du ${snapshot.data!.receivedAt.toLocal()}',
                            ),
                          ),
                          TextButton(
                            onPressed: refresh,
                            child: const Text('Réessayer'),
                          ),
                        ],
                      ),
                    ),
                  Expanded(
                    child: relations
                        ? relationsBody(payload)
                        : SpacePilotSurface(payload: payload),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }

  Widget relationsBody(Map<String, dynamic> payload) {
    final sections = payload['sections'];
    if (sections is! Map || sections.isEmpty) {
      final limited = spaceMap(payload['authority'])?['scope'] == 'activity_limited';
      return MakoloEmptyState(
        title: limited
            ? 'Relations globales réservées aux autorités du Space.'
            : 'Aucune collection relationnelle visible dans ce contexte.',
        icon: Icons.lock_outline,
      );
    }
    final query = searchController.text.trim();
    final matches = results?['items'];
    final groups = <String, List<Map<String, dynamic>>>{};
    if (query.isNotEmpty && matches is List) {
      final rows = <Map<String, dynamic>>[];
      for (final item in matches) {
        if (item is Map) rows.add(Map<String, dynamic>.from(item));
      }
      groups['Résultats'] = rows;
    } else {
      for (final entry in sections.entries) {
        final section = entry.value;
        if (section is! Map || section['items'] is! List) continue;
        final rows = <Map<String, dynamic>>[];
        for (final item in section['items'] as List) {
          if (item is Map) {
            final row = Map<String, dynamic>.from(item);
            if (query.isEmpty ||
                labelOf(row).toLowerCase().contains(query.toLowerCase())) {
              rows.add(row);
            }
          }
        }
        groups[spaceRelationshipSectionLabels[entry.key] ?? 'Relations'] = rows;
      }
    }
    return ListView(
      key: const Key('space-relationships-secondary'),
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          spaceText(payload['label']) ?? 'Personnes & relations',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        TextField(
          controller: searchController,
          maxLength: 120,
          onChanged: (_) {
            searchVersion++;
            setState(() {
              results = null;
              searchFailed = false;
            });
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
        if (query.isNotEmpty && results == null)
          const Text(
            'Aperçu local partiel. Lancez la recherche pour consulter toutes les relations autorisées.',
          ),
        if (groups.values.every((rows) => rows.isEmpty))
          const Text(
            'Aucune relation correspondante dans les données visibles.',
          ),
        for (final entry in groups.entries) ...[
          if (entry.value.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                entry.key,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
          for (final row in entry.value)
            SpaceRelationshipCard(
              row: row,
              onOpen: _relationRoute(row) == null
                  ? null
                  : () async {
                      final spaceId = actor?.space.id;
                      await context.push(_relationRoute(row)!);
                      if (!mounted || actor?.space.id != spaceId) return;
                      searchVersion++;
                      setState(() {
                        results = null;
                        searchFailed = false;
                        searchController.clear();
                      });
                      await refresh();
                    },
            ),
        ],
        if (query.isEmpty &&
            sections.values.any(
              (section) => section is Map && section['has_more'] == true,
            ))
          const Text(
            'Aperçu partiel. Recherchez pour retrouver les autres relations.',
          ),
        if (results?['has_more'] == true)
          const Text('Autres résultats possibles : affinez la recherche.'),
      ],
    );
  }

  String? _relationRoute(Map<String, dynamic> row) => spaceOwnerRoute(
    slug: actor?.space.slug,
    kind: spaceText(row['kind']),
    id: spaceText(row['id']),
  );

  String labelOf(Map<String, dynamic> row) {
    final profile = row['profile'];
    if (row['identity'] is String) return row['identity'] as String;
    if (profile is Map && profile['name'] is String) {
      return profile['name'] as String;
    }
    return row['name']?.toString() ?? row['label']?.toString() ?? 'Relation';
  }
}
