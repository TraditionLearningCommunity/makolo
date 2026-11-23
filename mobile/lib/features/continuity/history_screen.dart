import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

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
  int _searchGeneration = 0;
  bool _loadingMore = false;
  bool _loadFailed = false;
  bool _mayLoadNext = false;
  String? _lastRequested;
  _HistoryView? _loadedView;
  final ScrollController _scroll = ScrollController();
  bool _requestedInitialRefresh = false;
  bool _acquiringHistory = false;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_checkEnd);
    unawaited(_acquireOrRefresh());
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _checkEnd() {
    final current = _loadedView;
    if (!_scroll.hasClients ||
        _scroll.position.extentAfter >= 480 ||
        !_mayLoadNext ||
        _loadFailed ||
        _loadingMore ||
        _searching ||
        current == null ||
        !current.hasMore) {
      return;
    }
    final key =
        '$_query:$_filter:${current.nextOffset}:${_remoteHistory != null}';
    if (_lastRequested == key) return;
    _lastRequested = key;
    if (_remoteHistory == null) {
      unawaited(_loadMore(current));
    } else {
      unawaited(_remoteSearch(more: true));
    }
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final first = await widget.repository.readPage(offset: 0);
    final source = await widget.repository.readFirstPageSource();
    if (!mounted || source.invalidated) return;
    if (first == null ||
        HistoryRepository.freshnessPolicy.evaluate(
              first,
              now: DateTime.now(),
              invalidated: source.invalidated,
            ) !=
            FreshnessState.fresh) {
      await _refreshFirst();
    }
    if (mounted) unawaited(_acquireRemainingHistory());
  }

  Future<void> _acquireRemainingHistory() async {
    if (_acquiringHistory) return;
    _acquiringHistory = true;
    try {
      // Persist available owner pages directly into the Profile database.
      await widget.repository.prepareHistoryOffline(
        shouldContinue: () => mounted,
      );
    } on Object {
      // Previously acquired pages remain visible on network failure.
    } finally {
      _acquiringHistory = false;
    }
  }

  Future<void> _refreshFirst() async {
    if (_refreshing) return;
    setState(() {
      _refreshing = true;
      _loadFailed = false;
      _lastRequested = null;
    });
    try {
      await widget.repository.refreshPage(offset: 0);
    } on Object {
      // Existing pages remain readable.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _loadMore(_HistoryView view) async {
    if (_loadingMore || !view.hasMore || _loadFailed) return;
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshPage(offset: view.nextOffset);
      final received = await widget.repository.readPage(
        offset: view.nextOffset,
      );
      if (received == null) {
        throw StateError('History continuation unavailable');
      }
    } on Object {
      // Keep the currently cached history for retry.
      if (mounted) {
        _lastRequested = null;
        setState(() => _loadFailed = true);
      }
    } finally {
      if (mounted) {
        setState(() => _loadingMore = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _checkEnd();
        });
      }
    }
  }

  /// Reopen the exact owner search previously received on this Profile.
  /// The unfiltered pages remain independently searchable at all times.
  Future<void> _restoreCachedSearch() async {
    final generation = ++_searchGeneration;
    final query = _query;
    final filter = _filter;
    if (query.isEmpty && filter == 'all') return;
    final rows = await widget.repository.readCachedSearchPages(
      query: query,
      type: _serverFilter(filter),
    );
    if (!mounted ||
        generation != _searchGeneration ||
        query != _query ||
        filter != _filter) {
      return;
    }
    setState(() {
      _remotePages = rows;
      _remoteHistory = rows.isEmpty ? null : _HistoryView.fromPages(rows);
    });
  }

  static String _serverFilter(String filter) => switch (filter) {
    'access' => 'accesses',
    'journey' => 'journeys',
    _ => 'all',
  };

  Future<void> _remoteSearch({bool more = false}) async {
    if (_searching) return;
    final generation = ++_searchGeneration;
    final query = _query;
    final filter = _filter;
    setState(() {
      _searching = true;
      if (!more) {
        _loadFailed = false;
        _lastRequested = null;
      }
    });
    try {
      final nextOffset = more && _remoteHistory != null
          ? _remoteHistory!.nextOffset
          : 0;
      final payload = await widget.repository.searchPage(
        query: query,
        offset: nextOffset,
        type: _serverFilter(filter),
      );
      if (!mounted ||
          generation != _searchGeneration ||
          _query != query ||
          _filter != filter) {
        return;
      }
      final snapshot = StoredProjection(
        kind: HistoryRepository.searchProjectionKind,
        resourceKey: HistoryRepository.searchResourceKey(
          query: query,
          type: _serverFilter(filter),
          offset: nextOffset,
        ),
        schemaVersion: 1,
        payload: payload,
        receivedAt: DateTime.now(),
      );
      setState(() {
        _remotePages = more ? [..._remotePages, snapshot] : [snapshot];
        _remoteHistory = _HistoryView.fromPages(_remotePages);
      });
    } on Object {
      if (mounted &&
          generation == _searchGeneration &&
          _query == query &&
          _filter == filter) {
        // Preserve the already available local History on remote failure.
        _lastRequested = null;
        setState(() => _loadFailed = true);
      }
    } finally {
      if (mounted &&
          generation == _searchGeneration &&
          _query == query &&
          _filter == filter) {
        setState(() => _searching = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _checkEnd();
        });
      }
    }
  }

  /// A received event stays inspectable without navigating to an owner
  /// depth that may require the network. Opening that depth is optional.
  Future<void> _showKnownEvent(_HistoryItem item) async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.title,
                style: Theme.of(sheetContext).textTheme.titleLarge,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              if (item.occurredAt != null) Text(item.occurredAt!),
              if (item.outcome != null) Text(item.outcome!),
              if (item.id != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                FilledButton.tonal(
                  onPressed: () {
                    Navigator.of(sheetContext).pop();
                    widget.onOpenResource(item.kind, item.id!);
                  },
                  child: const Text('Ouvrir le détail'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
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
                  child: Text('Cet historique n’est plus accessible.'),
                ),
              );
            }
            final view = source.invalidated
                ? _HistoryView.fromPages(const [])
                : _HistoryView.fromPages(pages);
            // Merge local title matches with previously received owner search
            // results. A server match can come from fields other than title,
            // so it must not be discarded by a second client text filter.
            final visible = <_HistoryItem>[];
            final seen = <String>{};
            void collect(_HistoryItem item) {
              if (_filter != 'all' && item.kind != _filter) return;
              final key =
                  '${item.kind}:${item.id ?? item.title}:'
                  '${item.occurredAt ?? ''}';
              if (seen.add(key)) visible.add(item);
            }

            // A specifically searched owner result wins over an older
            // unfiltered snapshot of the same event.
            for (final item
                in _remoteHistory?.items ?? const <_HistoryItem>[]) {
              collect(item);
            }
            for (final item in view.items) {
              if (_query.isEmpty ||
                  item.title.toLowerCase().contains(_query.toLowerCase())) {
                collect(item);
              }
            }
            final effectiveView = _remoteHistory ?? view;
            _loadedView = effectiveView;
            _mayLoadNext =
                !source.invalidated &&
                source.lastErrorCode == null &&
                source.reachability != ReachabilityState.unreachable &&
                ((_query.isEmpty && _filter == 'all') ||
                    _remoteHistory != null);
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) _checkEnd();
            });
            final first = effectiveView.firstPage ?? view.firstPage;
            final wide =
                MediaQuery.sizeOf(context).width >= 900 &&
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
                  ? effectiveView.items.isEmpty
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
                  MakoloIconActionButton(
                    tooltip: 'Rechercher dans Makolo',
                    onPressed: () => context.push('/search'),
                    icon: Icons.search,
                  ),
                  MakoloIconActionButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refreshFirst,
                    icon: Icons.refresh_rounded,
                  ),
                ],
              ),
              body: MakoloSurfaceStateView(
                state: surface,
                empty: const MakoloEmptyState(
                  title: 'Aucun historique à afficher',
                  body: 'Vous retrouverez ici vos démarches et accès passés.',
                ),
                initialLoading: const SizedBox.expand(),
                onRetry: _refreshFirst,
                content: Row(
                  children: [
                    Expanded(
                      flex: 3,
                      child: ListView(
                        controller: _scroll,
                        key: const Key('history-content'),
                        padding: const EdgeInsets.all(MakoloSpacing.inner),
                        children: [
                          TextField(
                            decoration: const InputDecoration(
                              labelText: 'Rechercher dans mon historique',
                              prefixIcon: Icon(Icons.search),
                            ),
                            onChanged: (value) {
                              setState(() {
                                _searchGeneration++;
                                _searching = false;
                                _query = value.trim();
                                _remoteHistory = null;
                                _remotePages = [];
                                _selectedHistoryKey = null;
                                _lastRequested = null;
                                _loadFailed = false;
                              });
                              unawaited(_restoreCachedSearch());
                            },
                            onSubmitted: (_) => _remoteSearch(),
                          ),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 8,
                            children: [
                              for (final filter in const [
                                'all',
                                'access',
                                'journey',
                              ])
                                ChoiceChip(
                                  label: Text(
                                    filter == 'all'
                                        ? 'Tout'
                                        : filter == 'access'
                                        ? 'Accès'
                                        : 'Démarches',
                                  ),
                                  selected: _filter == filter,
                                  onSelected: (_) {
                                    setState(() {
                                      _searchGeneration++;
                                      _searching = false;
                                      _filter = filter;
                                      _remoteHistory = null;
                                      _remotePages = [];
                                      _selectedHistoryKey = null;
                                      _lastRequested = null;
                                      _loadFailed = false;
                                    });
                                    unawaited(_restoreCachedSearch());
                                  },
                                ),
                            ],
                          ),
                          const SizedBox(height: MakoloSpacing.sm),
                          Align(
                            alignment: Alignment.centerRight,
                            child: MakoloIconActionButton(
                              tooltip: 'Rechercher dans l’historique',
                              onPressed: _searching ? null : _remoteSearch,
                              icon: Icons.search,
                            ),
                          ),
                          if (_searching) const LinearProgressIndicator(),

                          if (visible.isEmpty)
                            const Text(
                              'Aucun résultat correspondant parmi les '
                              'éléments disponibles.',
                            ),
                          for (
                            var index = 0;
                            index < visible.length;
                            index++
                          ) ...[
                            _HistoryCard(
                              item: visible[index],
                              onOpen: (kind, id) {
                                if (wide) {
                                  setState(
                                    () => _selectedHistoryKey = '$kind:$id',
                                  );
                                } else {
                                  unawaited(_showKnownEvent(visible[index]));
                                }
                              },
                            ),
                            if (index < visible.length - 1)
                              const SizedBox(height: MakoloSpacing.sm),
                          ],
                          if (effectiveView.hasMore &&
                              (_loadingMore || _searching))
                            const Center(
                              child: Padding(
                                padding: EdgeInsets.all(MakoloSpacing.md),
                                child: CircularProgressIndicator.adaptive(),
                              ),
                            ),
                          if (_loadFailed)
                            Center(
                              child: MakoloActionButton(
                                label: 'Réessayer',
                                appearance: MakoloActionAppearance.quiet,
                                onPressed: () {
                                  setState(() {
                                    _loadFailed = false;
                                    _lastRequested = null;
                                  });
                                  if (_remoteHistory == null) {
                                    unawaited(_loadMore(view));
                                  } else {
                                    unawaited(_remoteSearch(more: true));
                                  }
                                },
                              ),
                            ),
                          if (!_loadFailed &&
                              !_loadingMore &&
                              !_searching &&
                              !effectiveView.hasMore &&
                              visible.isNotEmpty &&
                              source.lastErrorCode == null &&
                              source.reachability !=
                                  ReachabilityState.unreachable &&
                              ((_query.isEmpty && _filter == 'all') ||
                                  _remoteHistory != null))
                            const Center(
                              child: Padding(
                                padding: EdgeInsets.all(MakoloSpacing.md),
                                child: Text('Vous avez tout vu'),
                              ),
                            ),
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
                                MakoloActionButton(
                                  label: 'Voir les détails',
                                  appearance: MakoloActionAppearance.secondary,
                                  onPressed: () => widget.onOpenResource(
                                    chosen.kind,
                                    chosen.id!,
                                  ),
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
        leading: Icon(
          _kindIcon(item.kind),
          color: Theme.of(context).colorScheme.primary,
        ),
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

  IconData _kindIcon(String kind) {
    return switch (kind) {
      'journey' => Icons.timeline_outlined,
      'activity' || 'occurrence' => Icons.event_outlined,
      'order' || 'offer' => Icons.shopping_bag_outlined,
      'access' => Icons.badge_outlined,
      'payment' => Icons.payments_outlined,
      'form' || 'document' => Icons.description_outlined,
      'message' || 'conversation' => Icons.chat_bubble_outline_rounded,
      _ => Icons.history_rounded,
    };
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
    final stored = _map(page.payload['page']);
    if (stored['offset'] is num) return (stored['offset'] as num).toInt();
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
