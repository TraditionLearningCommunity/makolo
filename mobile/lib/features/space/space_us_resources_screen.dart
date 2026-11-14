import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../sync/owner_source_state.dart';
import '../resources/resource_presentation.dart';

/// Nous N2: institutional Resources projected for the active Space.
///
/// Moi and Nous share the same presentation. The underlying owners remain
/// distinct and viewer-aware; cached Space resources are observations only.
class SpaceUsResourcesScreen extends StatefulWidget {
  const SpaceUsResourcesScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });

  final AppRuntime runtime;
  final String slug;

  @override
  State<SpaceUsResourcesScreen> createState() => _SpaceUsResourcesScreenState();
}

class _SpaceUsResourcesScreenState extends State<SpaceUsResourcesScreen> {
  bool _refreshing = false;

  SpaceActorContext? get _actor {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == widget.slug
        ? actor
        : null;
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_ensure());
    });
  }

  @override
  void didUpdateWidget(covariant SpaceUsResourcesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime || oldWidget.slug != widget.slug) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_ensure());
      });
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  void _onActorChanged() {
    if (!mounted) return;
    setState(() => _refreshing = false);
    unawaited(_ensure());
  }

  Future<void> _ensure() async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    try {
      await repository.ensureResources(actor.space);
    } on Object {
      // Keep the last acquired projection.
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    final expectedId = actor.space.id;
    setState(() => _refreshing = true);
    try {
      await repository.refreshResources(actor.space);
      // Nous owns the institutional handoffs shown alongside Resource counts.
      // Reconcile it too, without making its availability a prerequisite for
      // keeping the Resource snapshot visible.
      await repository.refreshUs(actor.space);
    } on Object {
      // Local-first: preserve the last acquired Resource projection.
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _refreshing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null) {
      return ResourceHubScaffold(
        title: 'Nos ressources',
        refreshing: false,
        onRefresh: _refresh,
        entries: const [],
        emptyMessage: 'Choisissez cet Espace pour consulter ses ressources.',
      );
    }

    final resourceSource = repository.resourcesSource(actor.space);
    return StreamBuilder<OwnerSourceState>(
      stream: repository.watchSource(resourceSource),
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final state = sourceSnapshot.data ?? OwnerSourceState.unknown;
        return StreamBuilder(
          stream: repository.watchResources(actor.space),
          builder: (context, resourceSnapshot) {
            final resourcePayload = resourceSnapshot.data?.payload;

            if (state.invalidated) {
                  return ResourceHubScaffold(
                    title: 'Nos ressources',
                    refreshing: _refreshing,
                    onRefresh: _refresh,
                    entries: const [],
                    emptyMessage: 'Ces ressources ne sont pas accessibles avec vos droits actuels.',
                  );
                }

                if (resourcePayload == null) {
                  return ResourceHubScaffold(
                    title: 'Nos ressources',
                    refreshing: _refreshing,
                    onRefresh: _refresh,
                    entries: const [],
                    emptyMessage: state.lastErrorCode == null
                        ? 'Ressources en cours de chargement.'
                        : 'Ressources indisponibles.',
                  );
                }

                final counts = _map(resourcePayload['counts']);
                int? visibleCount(String key) {
                  final value = _int(counts[key]) ?? 0;
                  return value > 0 ? value : null;
                }

                final entries = <ResourceHubEntryData>[
                  ResourceHubEntryData(
                    key: const Key('space-resources-documents'),
                    icon: Icons.folder_copy_outlined,
                    title: 'Nos documents',
                    subtitle: 'Fichiers et pièces de cet Espace',
                    count: visibleCount('document'),
                    onTap: () =>
                        context.push('/space/${widget.slug}/us/documents'),
                  ),
                  ResourceHubEntryData(
                    key: const Key('space-resources-assets'),
                    icon: Icons.photo_library_outlined,
                    title: 'Nos médias',
                    subtitle: 'Images réutilisables par cet Espace',
                    count: visibleCount('asset'),
                    onTap: () => context.push(
                      '/space/${widget.slug}/us/resources/asset',
                    ),
                  ),
                  ResourceHubEntryData(
                    key: const Key('space-resources-templates'),
                    icon: Icons.content_copy_outlined,
                    title: 'Nos modèles',
                    subtitle: 'Modèles de présentation réutilisables',
                    count: visibleCount('template'),
                    onTap: () => context.push(
                      '/space/${widget.slug}/us/resources/template',
                    ),
                  ),
                  ResourceHubEntryData(
                    key: const Key('space-resources-themes'),
                    icon: Icons.palette_outlined,
                    title: 'Nos thèmes',
                    subtitle: 'Thèmes de présentation réutilisables',
                    count: visibleCount('theme'),
                    onTap: () => context.push(
                      '/space/${widget.slug}/us/resources/theme',
                    ),
                  ),
                  ResourceHubEntryData(
                    key: const Key('space-resources-credentials'),
                    icon: Icons.workspace_premium_outlined,
                    title: 'Titres émis',
                    subtitle:
                        'Attestations et certificats délivrés par cet Espace',
                    count: visibleCount('credential'),
                    onTap: () => context.push(
                      '/space/${widget.slug}/us/resources/credential',
                    ),
                  ),
                  ResourceHubEntryData(
                    key: const Key('space-resources-received-titles'),
                    icon: Icons.verified_outlined,
                    title: 'Titres reçus',
                    subtitle:
                        'Certificats et attestations acquis par cet Espace',
                    count: visibleCount('received_title'),
                    onTap: () => context.push(
                      '/space/${widget.slug}/us/resources/received_title',
                    ),
                  ),
                ];

            return ResourceHubScaffold(
              title: 'Nos ressources',
              refreshing: _refreshing,
              onRefresh: _refresh,
              entries: entries,
            );
          },
        );
      },
    );
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

int? _int(Object? value) =>
    value is num ? value.toInt() : int.tryParse('${value ?? ''}');
