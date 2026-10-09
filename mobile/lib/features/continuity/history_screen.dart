import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
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
  String _query = '';
  String _filter = 'all';
  _HistoryView? _remoteHistory;
  String? _selectedHistoryKey;
  List<StoredProjection> _remotePages = [];
  bool _searching = false;
  bool _searchFailed = false;
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

  Future<void> _remoteSearch({bool more = false}) async {
    final query = _query;
    final filter = _filter;
    setState(() {
      _searching = true;
      _searchFailed = false;
    });
    try {
      final nextOffset =
          more && _remoteHistory != null ? _remoteHistory!.nextOffset : 0;
      final payload = await widget.repository.searchPage(
        query: query,
        offset: nextOffset,
        type: filter == 'access'
            ? 'accesses'
            : filter == 'journey'
                ? 'journeys'
                : 'all',
      );
      if (!mounted || _query != query || _filter != filter) return;
      final snapshot = StoredProjection(
        kind: HistoryRepository.projectionKind,
        resourceKey: 'offset:$nextOffset:limit:24',
        schemaVersion: 1,
        payload: payload,
        receivedAt: DateTime.now(),
      );
      setState(() {
        _remotePages = more ? [..._remotePages, snapshot] : [snapshot];
        _remoteHistory = _HistoryView.fromPages(_remotePages);
      });
    } on Object {
      if (mounted && _query == query && _filter == filter) {
        setState(() => _searchFailed = true);
      }
    } finally {
      if (mounted && _query == query && _filter == filter) {
        setState(() => _searching = false);
      }
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
            if (source.invalidated) {
              return Scaffold(
                appBar: AppBar(title: const Text('Historique')),
                body: const Center(
                  child: Text(
                    'Cet historique n’est plus disponible avec '
                    'l’autorité actuelle.',
                  ),
                ),
              );
            }
            final view = source.invalidated
                ? _HistoryView.fromPages(const [])
                : _HistoryView.fromPages(pages);
            final visible = (_remoteHistory ?? view).items.where((item) {
              if (_filter != 'all' && item.kind != _filter) return false;
              return _query.isEmpty ||
                  item.title.toLowerCase().contains(_query.toLowerCase());
            }).toList();
            final first = view.firstPage ?? _remoteHistory?.firstPage;
            final wide = MediaQuery.sizeOf(context).width >= 900 &&
                MediaQuery.textScalerOf(context).scale(16) < 26;
            _HistoryItem? selected;
            for (final item in visible) {
              if ('${item.kind}:${item.id}' == _selectedHistoryKey) {
                selected = item;
                break;
              }
            }
            final chosen = selected;
            final freshness = first == null
                ? null
                : HistoryRepository.freshnessPolicy.evaluate(
                    first,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = first != null && !source.invalidated;
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
                    tooltip: 'Recherche transverse',
                    onPressed: () => context.push('/search'),
                    icon: const Icon(Icons.search),
                  ),
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
                content: Row(
                  children: [
                    Expanded(
                      flex: 3,
                      child: ListView(
                  key: const Key('history-content'),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  children: [
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'Rechercher dans l’historique synchronisé',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onChanged: (value) => setState(() {
                        _query = value.trim();
                        _remoteHistory = null;
                        _remotePages = [];
                        _selectedHistoryKey = null;
                      }),
                      onSubmitted: (_) => _remoteSearch(),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      children: [
                        for (final filter in const ['all', 'access', 'journey'])
                          ChoiceChip(
                            label: Text(filter == 'all'
                                ? 'Tout'
                                : filter == 'access'
                                    ? 'Accès'
                                    : 'Démarches'),
                            selected: _filter == filter,
                            onSelected: (_) {
                              setState(() {
                                _filter = filter;
                                _remoteHistory = null;
                                _remotePages = [];
                                _selectedHistoryKey = null;
                              });
                              unawaited(_remoteSearch());
                            },
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        const Expanded(
                          child: Text(
                            'Historique partiel. Résultats locaux puis '
                            'actualisation chez les propriétaires.',
                          ),
                        ),
                        IconButton(
                          tooltip: 'Rechercher dans tout l’historique visible',
                          onPressed: _searching ? null : _remoteSearch,
                          icon: const Icon(Icons.search),
                        ),
                      ],
                    ),
                    if (_searching) const LinearProgressIndicator(),
                    if (_searchFailed)
                      const Text(
                        'Recherche distante indisponible. '
                        'Les pages locales restent consultables.',
                      ),
                    if (visible.isEmpty)
                      const Text('Aucun élément correspondant parmi les '
                          'pages synchronisées.'),
                    for (var index = 0; index < visible.length; index++) ...[
                      _HistoryCard(
                        item: visible[index],
                        onOpen: (kind, id) {
                          if (wide) {
                            setState(() => _selectedHistoryKey = '$kind:$id');
                          } else {
                            widget.onOpenResource(kind, id);
                          }
                        },
                      ),
                      if (index < visible.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                    if ((_remoteHistory ?? view).hasMore) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      OutlinedButton(
                        onPressed: _loadingMore || _searching
                            ? null
                            : _remoteHistory == null
                                ? () => _loadMore(view)
                                : () => _remoteSearch(more: true),
                        child: Text(
                          _loadingMore || _searching
                              ? 'Chargement…'
                              : 'Afficher la suite',
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (wide && chosen != null) ...[
                const VerticalDivider(width: 1),
                Expanded(
                  flex: 2,
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          chosen.title,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 12),
                        if (chosen.outcome != null) Text(chosen.outcome!),
                        Text(chosen.occurredAt ?? 'Date non précisée'),
                        const SizedBox(height: 20),
                        if (chosen.id != null)
                          OutlinedButton(
                            onPressed: () => widget.onOpenResource(
                              chosen.kind, chosen.id!,
                            ),
                            child: const Text('Ouvrir chez le propriétaire'),
                          ),
                      ],
                    ),
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
        status: item.outcome == null
            ? null
            : MakoloStatus(label: item.outcome!),
        action: item.id == null
            ? null
            : const Icon(Icons.chevron_right_rounded),
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
        final sourceId = id ?? _string(row['title']) ?? '';
        final identity = '$kind:$sourceId';
        if (!seen.add(identity)) continue;
        final outcome = _map(row['outcome']);
        items.add(
          _HistoryItem(
            kind: kind,
            id: id,
            title: _string(row['title']) ?? 'Historique',
            occurredAt: row['time_quality'] == 'unknown_legacy'
                ? 'Date non précisée'
                : _humanInstant(row['occurred_at']),
            outcome:
                _string(outcome['label']) ??
                MakoloHumanization.presentationLabel(_string(outcome['code'])),
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

String? _humanInstant(Object? value) {
  final raw = _string(value);
  if (raw == null) return null;
  final instant = MakoloHumanization.tryParseInstant(raw);
  if (instant == null) return raw;
  return MakoloHumanization.formatDateTime(instant, now: DateTime.now());
}
