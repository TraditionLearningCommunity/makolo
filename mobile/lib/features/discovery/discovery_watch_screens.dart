import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';

class DiscoveryWatchSummary {
  const DiscoveryWatchSummary({
    required this.id,
    required this.name,
    required this.status,
  });

  final String id;
  final String name;
  final String status;
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
          status: _text(row['status']) ?? 'unknown',
        ),
      );
    }
    return List.unmodifiable(rows);
  }

  DiscoveryCollectionPresentation results(StoredProjection? projection) {
    return const DiscoverySelector().collection(projection);
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
  State<DiscoveryWatchesScreen> createState() =>
      _DiscoveryWatchesScreenState();
}

class _DiscoveryWatchesScreenState extends State<DiscoveryWatchesScreen> {
  static const _selector = DiscoveryWatchSelector();
  bool _refreshing = false;

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Veilles'),
        actions: [
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
                children: const [
                  SizedBox(height: 120),
                  Padding(
                    padding: EdgeInsets.all(MakoloSpacing.inner),
                    child: Center(
                      child: Text(
                        'Aucune veille enregistrée.',
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
            child: ListView.separated(
              padding: const EdgeInsets.all(MakoloSpacing.inner),
              itemCount: watches.length,
              separatorBuilder: (_, _) =>
                  const SizedBox(height: MakoloSpacing.sm),
              itemBuilder: (context, index) {
                final watch = watches[index];
                return MakoloCard(
                  onTap: () => widget.onOpenWatch(watch.id),
                  semanticLabel: 'Veille. ${watch.name}',
                  child: MakoloStatusMetadataAction(
                    title: watch.name,
                    status: MakoloStatus(label: watch.status),
                    action: const Icon(Icons.chevron_right_rounded),
                  ),
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
      await widget.repository.refreshWatchResults(
        widget.watchId,
        page: _page,
      );
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
                        'Cette veille ne retourne aucune possibilité actuellement.',
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
                      if (item.family == 'activity' ||
                          item.family == 'service_activity') {
                        widget.onOpenActivity(item.id);
                      } else {
                        widget.onOpenItem(item.family, item.id);
                      }
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
                      onPressed: _page > 1
                          ? () => _movePage(_page - 1)
                          : null,
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
