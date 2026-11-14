import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'objective_repository.dart';

/// Shallow owner-backed collections. Project/Dossier organization is a
/// separate product chantier; these lists only open the existing details.
class ObjectiveCollectionScreen extends StatefulWidget {
  const ObjectiveCollectionScreen({
    super.key,
    required this.kind,
    required this.repository,
    required this.onOpenItem,
  });

  final ObjectiveDepth kind;
  final ObjectiveRepository repository;
  final ValueChanged<String> onOpenItem;

  @override
  State<ObjectiveCollectionScreen> createState() =>
      _ObjectiveCollectionScreenState();
}

class _ObjectiveCollectionScreenState extends State<ObjectiveCollectionScreen> {
  late Stream<List<StoredProjection>> _pages;
  late Stream<OwnerSourceState> _source;
  final ScrollController _scroll = ScrollController();
  bool _loadingFirst = false;
  bool _loadingMore = false;
  bool _failed = false;
  bool _offline = false;
  bool _hasFirst = false;
  _ObjectivePage? _visiblePage;
  String? _lastRequest;

  @override
  void initState() {
    super.initState();
    _bind();
    _scroll.addListener(_checkEnd);
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant ObjectiveCollectionScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.kind != widget.kind) {
      _bind();
      _failed = false;
      _loadingFirst = false;
      _loadingMore = false;
      _lastRequest = null;
      _visiblePage = null;
      unawaited(_acquire());
    }
  }

  void _bind() {
    _pages = widget.repository.watchCollection(widget.kind);
    _source = widget.repository.watchCollectionSource(widget.kind);
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _acquire() async {
    final repository = widget.repository;
    final kind = widget.kind;
    try {
      final first = await repository.readCollectionPage(kind, offset: 0);
      final source = await repository.readCollectionSource(kind, offset: 0);
      if (!mounted || repository != widget.repository || kind != widget.kind) {
        return;
      }
      if (first == null ||
          ObjectiveRepository.freshnessPolicy.evaluate(
                first,
                now: DateTime.now().toUtc(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        await _refreshFirst();
      }
    } on Object {
      if (mounted && repository == widget.repository && kind == widget.kind) {
        setState(() => _failed = true);
      }
    }
  }

  Future<void> _refreshFirst() async {
    if (_loadingFirst) return;
    final repository = widget.repository;
    final kind = widget.kind;
    setState(() {
      _loadingFirst = true;
      _failed = false;
      _lastRequest = null;
    });
    try {
      await repository.refreshCollectionPage(kind, offset: 0);
      final row = await repository.readCollectionPage(kind, offset: 0);
      final source = await repository.readCollectionSource(kind, offset: 0);
      if (row == null ||
          source.invalidated ||
          source.lastErrorCode != null ||
          source.lastSuccessAt == null) {
        throw StateError('Objective collection unavailable');
      }
    } on Object {
      if (mounted && repository == widget.repository && kind == widget.kind) {
        setState(() => _failed = true);
      }
    } finally {
      if (mounted && repository == widget.repository && kind == widget.kind) {
        setState(() => _loadingFirst = false);
      }
    }
  }

  void _checkEnd() {
    final page = _visiblePage;
    if (!_scroll.hasClients ||
        _scroll.position.extentAfter >= 480 ||
        _offline ||
        _failed ||
        _loadingMore ||
        _loadingFirst ||
        !_hasFirst ||
        page == null ||
        !page.hasMore) {
      return;
    }
    unawaited(_loadMore(page));
  }

  Future<void> _loadMore(_ObjectivePage page) async {
    final repository = widget.repository;
    final kind = widget.kind;
    final key = '${kind.name}:${page.nextOffset}';
    if (_loadingMore || _failed || _offline || _lastRequest == key) return;
    _lastRequest = key;
    setState(() => _loadingMore = true);
    try {
      await repository.refreshCollectionPage(kind, offset: page.nextOffset);
      final received = await repository.readCollectionPage(
        kind,
        offset: page.nextOffset,
      );
      final source = await repository.readCollectionSource(
        kind,
        offset: page.nextOffset,
      );
      if (received == null ||
          source.invalidated ||
          source.lastErrorCode != null ||
          source.lastSuccessAt == null) {
        throw StateError('Objective continuation unavailable');
      }
    } on Object {
      if (mounted && repository == widget.repository && kind == widget.kind) {
        _lastRequest = null;
        setState(() => _failed = true);
      }
    } finally {
      if (mounted && repository == widget.repository && kind == widget.kind) {
        setState(() => _loadingMore = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _checkEnd();
        });
      }
    }
  }

  void _retry() {
    setState(() {
      _failed = false;
      _lastRequest = null;
    });
    final page = _visiblePage;
    if (page != null && _hasFirst && page.hasMore) {
      unawaited(_loadMore(page));
    } else {
      unawaited(_refreshFirst());
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDossier = widget.kind == ObjectiveDepth.dossier;
    final title = isDossier ? 'Mes dossiers' : 'Mes projets';
    final offline =
        SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: StreamBuilder<OwnerSourceState>(
        stream: _source,
        initialData: OwnerSourceState.unknown,
        builder: (context, sourceSnapshot) {
          final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
          _offline =
              offline || source.reachability == ReachabilityState.unreachable;
          if (source.invalidated) {
            return Center(
              child: Text(
                isDossier
                    ? 'Ces dossiers ne sont plus accessibles.'
                    : 'Ces projets ne sont plus accessibles.',
              ),
            );
          }
          return StreamBuilder<List<StoredProjection>>(
            stream: _pages,
            builder: (context, pagesSnapshot) {
              final page = _ObjectivePage.fromPages(
                pagesSnapshot.data ?? const [],
                widget.kind,
                widget.repository.profileId,
              );
              _visiblePage = page;
              _hasFirst = page.hasFirst;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) _checkEnd();
              });
              if (!_hasFirst && _loadingFirst) {
                return const Center(
                  child: CircularProgressIndicator.adaptive(),
                );
              }
              if (!_hasFirst && _failed) {
                return Center(
                  child: MakoloActionButton(
                    label: 'Réessayer',
                    onPressed: _retry,
                    appearance: MakoloActionAppearance.quiet,
                  ),
                );
              }
              final personal = page.items
                  .where((item) => item.relation == 'mine')
                  .toList();
              final other = page.items
                  .where((item) => item.relation != 'mine')
                  .toList();
              return RefreshIndicator(
                onRefresh: _refreshFirst,
                child: ListView(
                  key: PageStorageKey<String>(
                    'me-objectives-${widget.repository.profileId}-${widget.kind.name}',
                  ),
                  controller: _scroll,
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 36),
                  children: [
                    if (personal.isNotEmpty) ...[
                      Text(
                        isDossier
                            ? 'Mes dossiers personnels'
                            : 'Mes projets personnels',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      for (final item in personal)
                        _ObjectiveRow(
                          item: item,
                          onTap: () => widget.onOpenItem(item.id),
                        ),
                    ],
                    if (other.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text(
                        isDossier
                            ? 'Autres dossiers accessibles'
                            : 'Autres projets accessibles',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      for (final item in other)
                        _ObjectiveRow(
                          item: item,
                          onTap: () => widget.onOpenItem(item.id),
                        ),
                    ],
                    if (_hasFirst && page.items.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 28),
                        child: Center(
                          child: Text(
                            isDossier
                                ? 'Aucun dossier accessible pour le moment.'
                                : 'Aucun projet accessible pour le moment.',
                          ),
                        ),
                      ),
                    if (_loadingMore)
                      const Padding(
                        padding: EdgeInsets.all(16),
                        child: Center(
                          child: CircularProgressIndicator.adaptive(),
                        ),
                      ),
                    if (_failed && _hasFirst)
                      Center(
                        child: MakoloActionButton(
                          label: 'Réessayer',
                          onPressed: _retry,
                          appearance: MakoloActionAppearance.quiet,
                        ),
                      ),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _ObjectiveRow extends StatelessWidget {
  const _ObjectiveRow({required this.item, required this.onTap});

  final _ObjectiveItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final state = switch (item.state) {
      'draft' => 'En préparation',
      'active' => 'En cours',
      'completed' => 'Terminé',
      'cancelled' => 'Annulé',
      'archived' => 'Archivé',
      _ => 'État indisponible',
    };
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Card(
        margin: EdgeInsets.zero,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: scheme.outlineVariant),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          key: Key('objective-collection-row-${item.id}'),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 13),
            child: Row(
              children: [
                Icon(Icons.folder_outlined, color: scheme.primary, size: 25),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        [
                          if (item.space != null) item.space!,
                          state,
                        ].join(' · '),
                        style: Theme.of(context).textTheme.bodySmall
                            ?.copyWith(color: scheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right_rounded, color: scheme.primary),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ObjectiveItem {
  const _ObjectiveItem({
    required this.id,
    required this.title,
    required this.relation,
    required this.state,
    this.space,
  });
  final String id;
  final String title;
  final String relation;
  final String state;
  final String? space;
}

class _ObjectivePage {
  const _ObjectivePage({
    required this.items,
    required this.hasFirst,
    required this.hasMore,
    required this.nextOffset,
  });

  final List<_ObjectiveItem> items;
  final bool hasFirst;
  final bool hasMore;
  final int nextOffset;

  factory _ObjectivePage.fromPages(
    List<StoredProjection> projections,
    ObjectiveDepth kind,
    String profileId,
  ) {
    final ordered = projections.toList()
      ..sort((a, b) => _offset(a).compareTo(_offset(b)));
    final rows = <_ObjectiveItem>[];
    final seen = <String>{};
    var expected = 0;
    var hasFirst = false;
    var hasMore = false;
    for (final projection in ordered) {
      final data = projection.payload;
      final actor = data['actor'];
      final page = data['page'];
      final raw = data['items'];
      if (actor is! Map ||
          actor['type'] != 'profile' ||
          actor['id']?.toString() != profileId ||
          page is! Map ||
          raw is! List ||
          page['offset'] != expected) {
        break;
      }
      hasFirst = true;
      for (final candidate in raw) {
        if (candidate is! Map ||
            candidate['kind'] != kind.name ||
            candidate['id'] is! String ||
            candidate['title'] is! String) {
          continue;
        }
        final id = candidate['id'] as String;
        if (!seen.add(id)) continue;
        final space = candidate['space'];
        rows.add(
          _ObjectiveItem(
            id: id,
            title: candidate['title'] as String,
            relation: candidate['relation']?.toString() ?? 'shared',
            state: candidate['state']?.toString() ?? '',
            space: space is Map ? space['name']?.toString() : null,
          ),
        );
      }
      hasMore = page['has_more'] == true;
      final nextOffset = page['next_offset'];
      if (nextOffset is! int || nextOffset <= expected) {
        if (hasMore) break;
        expected += raw.length;
      } else {
        expected = nextOffset;
      }
      if (!hasMore) break;
    }
    return _ObjectivePage(
      items: rows,
      hasFirst: hasFirst,
      hasMore: hasMore,
      nextOffset: expected,
    );
  }

  static int _offset(StoredProjection snapshot) {
    final page = snapshot.payload['page'];
    return page is Map && page['offset'] is int ? page['offset'] as int : 0;
  }
}
