import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/interaction_primitives.dart';
import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';

import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../presentation/humanization.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';
import 'discovery_watch_create.dart';

class DiscoveryWatchSummary {
  const DiscoveryWatchSummary({
    required this.id,
    required this.name,
    this.status,
    this.statusCode,
    this.criteria = const {},
  });

  final String id;
  final String name;
  final String? status;
  final String? statusCode;
  final Map<String, String> criteria;
}

class DiscoveryWatchSelector {
  const DiscoveryWatchSelector();

  List<DiscoveryWatchSummary> list(StoredProjection? projection) {
    final results = projection?.payload['results'];
    if (results is! List) return const [];
    final rows = <DiscoveryWatchSummary>[];
    for (final raw in results.whereType<Map>()) {
      final row = Map<String, dynamic>.from(raw);
      final id = _text(row['id']);
      final name = _text(row['name']);
      if (id == null || name == null) continue;
      rows.add(
        DiscoveryWatchSummary(
          id: id,
          name: name,
          status: MakoloHumanization.presentationLabel(_text(row['status'])),
          statusCode: _text(row['status']),
          criteria: row['criteria'] is Map
              ? Map<String, String>.from(
                  (row['criteria'] as Map).map(
                    (key, value) => MapEntry(key.toString(), value.toString()),
                  ),
                )
              : const {},
        ),
      );
    }
    return List.unmodifiable(rows);
  }

  String description(DiscoveryWatchSummary watch) {
    final criteria = watch.criteria;
    final labels = <String>[
      if ((criteria['q'] ?? '').isNotEmpty) criteria['q']!,
      if ((criteria['place'] ?? '').isNotEmpty) criteria['place']!,
      if ((criteria['vertical'] ?? '').isNotEmpty)
        const {
              'event': 'Événements',
              'transport': 'Transports',
              'service': 'Services',
              'other': 'Autres activités',
            }[criteria['vertical']] ??
            criteria['vertical']!,
      if ((criteria['when'] ?? '').isNotEmpty)
        const {
              'today': 'Aujourd’hui',
              'tomorrow': 'Demain',
              'week': 'Cette semaine',
              'weekend': 'Ce week-end',
            }[criteria['when']] ??
            criteria['when']!,
      if ((criteria['date_from'] ?? '').isNotEmpty ||
          (criteria['date_to'] ?? '').isNotEmpty)
        [
          criteria['date_from'],
          criteria['date_to'],
        ].whereType<String>().where((value) => value.isNotEmpty).join(' → '),
      if ((criteria['price'] ?? '').isNotEmpty)
        criteria['price'] == 'free' ? 'Gratuit' : 'Payant',
    ];
    return labels.join(' · ');
  }

  DiscoveryCollectionPresentation results(StoredProjection? projection) {
    return const DiscoverySelector().watchCollection(projection);
  }
}

class DiscoveryWatchesScreen extends StatefulWidget {
  const DiscoveryWatchesScreen({
    super.key,
    required this.repository,
    required this.onOpenWatch,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenWatch;

  @override
  State<DiscoveryWatchesScreen> createState() => _DiscoveryWatchesScreenState();
}

class _DiscoveryWatchesScreenState extends State<DiscoveryWatchesScreen> {
  static const _selector = DiscoveryWatchSelector();
  bool _refreshing = false;
  String? _mutating;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  @override
  void didUpdateWidget(covariant DiscoveryWatchesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(widget.repository, oldWidget.repository)) {
      _refreshing = false;
      unawaited(_refresh());
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshWatches();
    } on Object {
      // Preserve any existing local Watch collection.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _create() async {
    final id = await showDiscoveryWatchCreation(
      context,
      repository: widget.repository,
      query: const DiscoveryQuery(),
    );
    if (mounted && id != null) {
      context.push('/discover/watches/${Uri.encodeComponent(id)}');
    }
  }

  Future<void> _change(DiscoveryWatchSummary watch, String action) async {
    if (_mutating != null) return;
    String? renamed;
    if (action == 'rename') {
      final controller = TextEditingController(text: watch.name);
      try {
        renamed = await showDialog<String>(
          context: context,
          builder: (dialog) => AlertDialog(
            title: const Text('Renommer la veille'),
            content: TextField(
              controller: controller,
              maxLength: 140,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Nom'),
            ),
            actions: [
              MakoloActionButton(
                label: 'Annuler',
                appearance: MakoloActionAppearance.quiet,
                onPressed: () => Navigator.pop(dialog),
              ),
              MakoloActionButton(
                label: 'Enregistrer',
                appearance: MakoloActionAppearance.primary,
                onPressed: () => Navigator.pop(dialog, controller.text.trim()),
              ),
            ],
          ),
        );
      } finally {
        controller.dispose();
      }
      if (renamed == null || !mounted) return;
    }
    if (action == 'criteria') {
      final id = await showDiscoveryWatchCreation(
        context,
        repository: widget.repository,
        query: DiscoveryQuery.fromRouteParameters(watch.criteria),
        watchId: watch.id,
        initialName: watch.name,
      );
      if (id != null && mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Veille modifiée.')));
      }
      return;
    }
    if (action == 'delete') {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: const Text('Supprimer cette veille ?'),
          content: Text(
            'La veille « ${watch.name} » sera supprimée. '
            'Cela ne supprime aucune possibilité enregistrée.',
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialog, false),
            ),
            MakoloActionButton(
              label: 'Supprimer',
              appearance: MakoloActionAppearance.danger,
              onPressed: () => Navigator.pop(dialog, true),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
    }
    setState(() => _mutating = watch.id);
    try {
      if (action == 'delete') {
        await widget.repository.deleteWatch(watch.id);
      } else if (action == 'rename') {
        await widget.repository.editWatch(watch.id, name: renamed!);
      } else {
        await widget.repository.updateWatchStatus(watch.id, action);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(switch (action) {
              'delete' => 'Veille supprimée.',
              'rename' => 'Veille renommée.',
              'paused' => 'Veille mise en pause.',
              'active' => 'Veille réactivée.',
              _ => 'Veille mise à jour.',
            }),
          ),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Impossible de modifier cette veille. Réessayez.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _mutating = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Veilles'),
        actions: [
          MakoloIconActionButton(
            key: const Key('discover-watch-create'),
            tooltip: 'Créer une veille',
            onPressed: () => _create(),
            icon: Icons.add_rounded,
          ),
          MakoloIconActionButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: Icons.refresh_rounded,
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        key: ValueKey('discover-watches-${widget.repository.profileId}'),
        stream: widget.repository.watchWatches(),
        builder: (context, snapshot) {
          final watches = _selector.list(snapshot.data);
          if (snapshot.data == null) {
            return Center(
              child: _refreshing
                  ? const MakoloSkeleton(lines: 5)
                  : MakoloActionButton(
                      label: 'Réessayer',
                      onPressed: () => unawaited(_refresh()),
                      appearance: MakoloActionAppearance.secondary,
                    ),
            );
          }
          if (watches.isEmpty) {
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  const SizedBox(height: 88),
                  const Icon(Icons.radar_outlined, size: 44),
                  const SizedBox(height: 16),
                  const Center(child: Text('Aucune veille pour le moment.')),
                  const SizedBox(height: 10),
                  const SizedBox(height: 24),
                  Center(
                    child: MakoloActionButton(
                      label: 'Créer une veille',
                      onPressed: _create,
                      icon: Icons.add,
                      appearance: MakoloActionAppearance.primary,
                    ),
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.separated(
              padding: const EdgeInsets.all(MakoloSpacing.inner),
              itemCount: watches.length,
              separatorBuilder: (_, _) =>
                  const SizedBox(height: MakoloSpacing.sm),
              itemBuilder: (context, index) {
                final watch = watches[index];
                return Row(
                  children: [
                    Expanded(
                      child: MakoloCard(
                        onTap: () => widget.onOpenWatch(watch.id),
                        semanticLabel: 'Veille. ${watch.name}',
                        child: MakoloStatusMetadataAction(
                          title: watch.name,
                          subtitle: _selector.description(watch).isEmpty
                              ? null
                              : _selector.description(watch),
                          status: watch.status == null
                              ? null
                              : MakoloStatus(label: watch.status!),
                          action: const Icon(Icons.chevron_right_rounded),
                        ),
                      ),
                    ),
                    MakoloActionMenu(
                      key: ValueKey('discover-watch-manage-${watch.id}'),
                      tooltip: 'Gérer la veille',
                      onSelected: (action) =>
                          unawaited(_change(watch, action.id)),
                      actions: [
                        MakoloInteractionAction(
                          id: watch.statusCode == 'paused'
                              ? 'active'
                              : 'paused',
                          label: watch.statusCode == 'paused'
                              ? 'Reprendre'
                              : 'Mettre en pause',
                          intent: MakoloActionIntent.transition,
                          enabled: _mutating == null,
                        ),
                        MakoloInteractionAction(
                          id: 'rename',
                          label: 'Renommer',
                          intent: MakoloActionIntent.edit,
                          enabled: _mutating == null,
                        ),
                        MakoloInteractionAction(
                          id: 'criteria',
                          label: 'Modifier les critères',
                          intent: MakoloActionIntent.filter,
                          enabled: _mutating == null,
                        ),
                        MakoloInteractionAction(
                          id: 'delete',
                          label: 'Supprimer',
                          intent: MakoloActionIntent.more,
                          enabled: _mutating == null,
                          destructive: true,
                        ),
                      ],
                    ),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class DiscoveryWatchResultsScreen extends StatefulWidget {
  const DiscoveryWatchResultsScreen({
    super.key,
    required this.watchId,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
  });

  final String watchId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;

  @override
  State<DiscoveryWatchResultsScreen> createState() =>
      _DiscoveryWatchResultsScreenState();
}

class _DiscoveryWatchResultsScreenState
    extends State<DiscoveryWatchResultsScreen> {
  static const _selector = DiscoveryWatchSelector();
  bool _refreshing = false;
  int _page = 1;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant DiscoveryWatchResultsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.watchId != widget.watchId ||
        !identical(oldWidget.repository, widget.repository)) {
      _page = 1;
      _refreshing = false;
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() async {
    // Render the actor-scoped local page first, then refresh quietly.
    final watchId = widget.watchId;
    final repository = widget.repository;
    final page = _page;
    await repository.readWatchResults(watchId, page: page);
    if (!mounted ||
        !identical(repository, widget.repository) ||
        widget.watchId != watchId ||
        _page != page)
      return;
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshWatchResults(widget.watchId, page: _page);
    } on Object {
      // Preserve any cached replay page.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _movePage(int page) {
    if (page < 1) return;
    setState(() => _page = page);
    unawaited(_acquire());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Résultats de la veille'),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: Icons.refresh_rounded,
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        // A new Watch or Profile must not inherit a previous snapshot.
        key: ValueKey(
          'watch-results-${widget.repository.profileId}-${widget.watchId}-$_page',
        ),
        stream: widget.repository.watchWatchResults(
          widget.watchId,
          page: _page,
        ),
        builder: (context, snapshot) {
          final result = _selector.results(snapshot.data);
          if (snapshot.data == null) {
            return Center(
              child: _refreshing
                  ? const MakoloSkeleton(lines: 5)
                  : MakoloActionButton(
                      label: 'Réessayer',
                      onPressed: () => unawaited(_refresh()),
                      appearance: MakoloActionAppearance.secondary,
                    ),
            );
          }
          if (result.items.isEmpty) {
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [
                  SizedBox(height: 120),
                  Padding(
                    padding: EdgeInsets.all(MakoloSpacing.inner),
                    child: Center(
                      child: Text(
                        'Aucune correspondance pour le moment.',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              key: ValueKey('watch-${widget.watchId}-page-$_page'),
              padding: const EdgeInsets.all(MakoloSpacing.inner),
              children: [
                for (final item in result.items) ...[
                  MakoloCard(
                    onTap: () {
                      // Watch replays the canonical Discovery N2 identity,
                      // not an Activity-only depth or an engagement action.
                      widget.onOpenItem(item.family, item.id);
                    },
                    semanticLabel: 'Opportunité. ${item.title}',
                    child: MakoloStatusMetadataAction(
                      title: item.title,
                      subtitle: item.summary.isEmpty ? null : item.summary,
                      status: item.availability == null
                          ? null
                          : MakoloStatus(label: item.availability!),
                      action: const Icon(Icons.chevron_right_rounded),
                    ),
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
                Row(
                  children: [
                    MakoloActionButton(
                      label: 'Précédent',
                      onPressed: _page > 1 ? () => _movePage(_page - 1) : null,
                      appearance: MakoloActionAppearance.secondary,
                    ),
                    const Spacer(),
                    Text('Page $_page'),
                    const Spacer(),
                    MakoloActionButton(
                      label: 'Suivant',
                      onPressed: result.hasNext
                          ? () => _movePage(_page + 1)
                          : null,
                      appearance: MakoloActionAppearance.primary,
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

String? _text(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}
