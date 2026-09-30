import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'history_repository.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({
    super.key,
    required this.repository,
    required this.onOpenResource,
  });

  final HistoryRepository repository;
  final void Function(String kind, String id) onOpenResource;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _loadingMore = false;
  bool _requestedInitialRefresh = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final first = await widget.repository.readPage(offset: 0);
    final source = await widget.repository.readFirstPageSource();
    if (!mounted) return;
    if (first == null) {
      await _refreshFirst();
      return;
    }
    final freshness = HistoryRepository.freshnessPolicy.evaluate(
      first,
      now: DateTime.now(),
      invalidated: source.invalidated,
    );
    if (freshness != FreshnessState.fresh) await _refreshFirst();
  }

  Future<void> _refreshFirst() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshPage(offset: 0);
    } on Object {
      // Existing pages remain readable.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _loadMore(_HistoryView view) async {
    if (_loadingMore || !view.hasMore) return;
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshPage(offset: view.nextOffset);
    } on Object {
      // Keep the currently cached history.
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<StoredProjection>>(
      stream: widget.repository.watchCachedPages(),
      initialData: const [],
      builder: (context, pagesSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchFirstPageSource(),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final pages = pagesSnapshot.data ?? const [];
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final view = _HistoryView.fromPages(pages);
            final first = view.firstPage;
            final freshness = first == null
                ? null
                : HistoryRepository.freshnessPolicy.evaluate(
                    first,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = first != null;
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: first?.payload,
                freshness: freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? view.items.isEmpty
                        ? MakoloAvailabilityCue.empty
                        : MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: const Text('Historique'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refreshFirst,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloSurfaceStateView(
                state: surface,
                empty: const MakoloEmptyState(
                  title: 'Aucun historique à afficher',
                  body: 'Les expériences terminées apparaîtront ici.',
                ),
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement de l’historique…',
                ),
                onRetry: _refreshFirst,
                content: ListView(
                  key: const Key('history-content'),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  children: [
                    for (var index = 0; index < view.items.length; index++) ...[
                      _HistoryCard(
                        item: view.items[index],
                        onOpen: widget.onOpenResource,
                      ),
                      if (index < view.items.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                    if (view.hasMore) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      OutlinedButton(
                        onPressed:
                            _loadingMore ? null : () => _loadMore(view),
                        child: Text(
                          _loadingMore ? 'Chargement…' : 'Afficher la suite',
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _HistoryCard extends StatelessWidget {
  const _HistoryCard({required this.item, required this.onOpen});

  final _HistoryItem item;
  final void Function(String kind, String id) onOpen;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      onTap: item.id == null ? null : () => onOpen(item.kind, item.id!),
      child: MakoloStatusMetadataAction(
        title: item.title,
        subtitle: item.occurredAt,
        status: item.outcome == null ? null : MakoloStatus(label: item.outcome!),
        action: item.id == null ? null : const Icon(Icons.chevron_right_rounded),
      ),
    );
  }
}

class _HistoryView {
  const _HistoryView({
    required this.items,
    required this.hasMore,
    required this.nextOffset,
    this.firstPage,
  });

  final List<_HistoryItem> items;
  final bool hasMore;
  final int nextOffset;
  final StoredProjection? firstPage;

  factory _HistoryView.fromPages(List<StoredProjection> pages) {
    if (pages.isEmpty) {
      return const _HistoryView(items: [], hasMore: false, nextOffset: 0);
    }
    final ordered = pages.toList()
      ..sort((a, b) => _offset(a).compareTo(_offset(b)));
    final seen = <String>{};
    final items = <_HistoryItem>[];
    for (final page in ordered) {
      final rawItems = page.payload['items'];
      if (rawItems is! List) continue;
      for (final raw in rawItems) {
        final row = _map(raw);
        final source = _map(row['source']);
        final kind = _string(source['kind']) ?? _string(row['kind']) ?? '';
        final id = _string(source['id']);
        final identity = kind + ':' + (id ?? _string(row['title']) ?? '');
        if (!seen.add(identity)) continue;
        final outcome = _map(row['outcome']);
        items.add(
          _HistoryItem(
            kind: kind,
            id: id,
            title: _string(row['title']) ?? 'Historique',
            occurredAt: _string(row['occurred_at']),
            outcome:
                _string(outcome['label']) ?? _string(outcome['code']),
          ),
        );
      }
    }
    final last = ordered.last;
    final page = _map(last.payload['page']);
    final lastOffset = page['offset'] is num
        ? (page['offset'] as num).toInt()
        : _offset(last);
    final limit = page['limit'] is num
        ? (page['limit'] as num).toInt()
        : HistoryRepository.defaultLimit;
    return _HistoryView(
      items: items,
      hasMore: page['has_more'] == true,
      nextOffset: lastOffset + limit,
      firstPage: ordered.firstWhere(
        (page) => _offset(page) == 0,
        orElse: () => ordered.first,
      ),
    );
  }

  static int _offset(StoredProjection page) {
    final parts = page.resourceKey.split(':');
    if (parts.length >= 2 && parts.first == 'offset') {
      return int.tryParse(parts[1]) ?? 0;
    }
    return 0;
  }
}

class _HistoryItem {
  const _HistoryItem({
    required this.kind,
    required this.title,
    this.id,
    this.occurredAt,
    this.outcome,
  });

  final String kind;
  final String? id;
  final String title;
  final String? occurredAt;
  final String? outcome;
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}
