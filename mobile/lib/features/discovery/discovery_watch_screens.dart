import 'dart:async';

import 'package:flutter/material.dart';
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
              ? Map<String, String>.from((row['criteria'] as Map).map((key, value) => MapEntry(key.toString(), value.toString())))
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
        const {'event': 'Événements', 'transport': 'Transports',
          'service': 'Services', 'other': 'Autres activités'}[criteria['vertical']] ??
            criteria['vertical']!,
      if ((criteria['when'] ?? '').isNotEmpty)
        const {'today': 'Aujourd’hui', 'tomorrow': 'Demain',
          'week': 'Cette semaine', 'weekend': 'Ce week-end'}[criteria['when']] ??
            criteria['when']!,
      if ((criteria['date_from'] ?? '').isNotEmpty ||
          (criteria['date_to'] ?? '').isNotEmpty)
        [criteria['date_from'], criteria['date_to']]
            .whereType<String>().where((value) => value.isNotEmpty).join(' → '),
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
      context.push('/discover/watches/' + Uri.encodeComponent(id));
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
              TextButton(
                onPressed: () => Navigator.pop(dialog),
                child: const Text('Annuler'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialog, controller.text.trim()),
                child: const Text('Enregistrer'),
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Veille modifiée.')),
        );
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
            TextButton(
              onPressed: () => Navigator.pop(dialog, false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialog, true),
              child: const Text('Supprimer'),
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
            content: Text(
              switch (action) {
                'delete' => 'Veille supprimée.',
                'rename' => 'Veille renommée.',
                'paused' => 'Veille mise en pause.',
                'active' => 'Veille réactivée.',
                _ => 'Veille mise à jour.',
              },
            ),
          ),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Impossible de modifier cette veille. Réessayez.',
            ),
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
          IconButton(
            key: const Key('discover-watch-create'),
            tooltip: 'Créer une veille',
            onPressed: () => _create(),
            icon: const Icon(Icons.add_rounded),
          ),
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchWatches(),
        builder: (context, snapshot) {
          final watches = _selector.list(snapshot.data);
          if (snapshot.data == null) {
            return Center(
              child: _refreshing
                  ? const CircularProgressIndicator()
                  : OutlinedButton(
                      onPressed: () => unawaited(_refresh()),
                      child: const Text('Réessayer'),
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
                  const Center(child: Text('Aucune veille enregistrée.')),
                  const SizedBox(height: 10),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 28),
                    child: Text(
                      'Indiquez ce que Makolo doit continuer à rechercher pour vous.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 24),
                  Center(child: FilledButton.icon(
                    onPressed: _create,
                    icon: const Icon(Icons.add),
                    label: const Text('Créer une veille'),
                  )),
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
                              ? null : _selector.description(watch),
                          status: watch.status == null
                              ? null
                              : MakoloStatus(label: watch.status!),
                          action: const Icon(Icons.chevron_right_rounded),
                        ),
                      ),
                    ),
                    PopupMenuButton<String>(
                      key: ValueKey('discover-watch-manage-${watch.id}'),
                      enabled: _mutating == null,
                      tooltip: 'Gérer la veille',
                      onSelected: (action) => unawaited(_change(watch, action)),
                      itemBuilder: (_) => [
                        PopupMenuItem(
                          value: watch.statusCode == 'paused'
                              ? 'active'
                              : 'paused',
                          child: Text(
                            watch.statusCode == 'paused'
                                ? 'Reprendre'
                                : 'Mettre en pause',
                          ),
                        ),
                        const PopupMenuItem(
                          value: 'rename',
                          child: Text('Renommer'),
                        ),
                        const PopupMenuItem(
                          value: 'criteria',
                          child: Text('Modifier les critères'),
                        ),
                        const PopupMenuItem(
                          value: 'delete',
                          child: Text('Supprimer'),
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

  Future<void> _acquire() async {
    final local = await widget.repository.readWatchResults(
      widget.watchId,
      page: _page,
    );
    if (local == null) await _refresh();
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
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchWatchResults(
          widget.watchId,
          page: _page,
        ),
        builder: (context, snapshot) {
          final result = _selector.results(snapshot.data);
          if (snapshot.data == null) {
            return Center(
              child: _refreshing
                  ? const CircularProgressIndicator()
                  : OutlinedButton(
                      onPressed: () => unawaited(_refresh()),
                      child: const Text('Réessayer'),
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
                        'Aucune possibilité trouvée pour cette veille.',
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
                    semanticLabel: 'Possibilité. ${item.title}',
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
                    OutlinedButton(
                      onPressed: _page > 1 ? () => _movePage(_page - 1) : null,
                      child: const Text('Précédent'),
                    ),
                    const Spacer(),
                    Text('Page $_page'),
                    const Spacer(),
                    FilledButton(
                      onPressed: result.hasNext
                          ? () => _movePage(_page + 1)
                          : null,
                      child: const Text('Suivant'),
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
