import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../sync/freshness.dart';
import 'resource_presentation.dart';
import 'resource_repository.dart';

class DocumentsScreen extends StatefulWidget {
  const DocumentsScreen({
    super.key,
    required this.repository,
    required this.onOpenDocument,
    required this.onAddDocument,
  });

  final ResourceRepository repository;
  final ValueChanged<String> onOpenDocument;
  final VoidCallback onAddDocument;

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen> {
  final _search = TextEditingController();
  final _scroll = ScrollController();
  Timer? _searchDebounce;

  String _query = '';
  String _view = 'current';
  String _kind = '';
  String _sensitivity = '';
  String _sort = 'recent';

  bool _initializing = true;
  bool _searching = false;
  bool _refreshing = false;
  bool _refreshFailed = false;
  bool _loadingMore = false;
  bool _loadFailed = false;
  bool _canLoadNext = false;
  String? _completedRequest;
  _DocumentsView? _visibleView;
  late Stream<List<StoredProjection>> _pages;
  late Stream<ResourceSourceState> _source;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_checkEnd);
    _pages = widget.repository.watchCollectionPages();
    _resetSource();
    unawaited(_ensureFirstPage());
  }

  @override
  void didUpdateWidget(covariant DocumentsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _pages = widget.repository.watchCollectionPages();
      _resetSource();
      unawaited(_ensureFirstPage());
    }
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _search.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _resetSource() {
    _source = widget.repository.watchCollectionSource(
      query: _query,
      view: _view,
      kind: _kind,
      sensitivity: _sensitivity,
      sort: _sort,
    );
  }

  void _checkEnd() {
    final view = _visibleView;
    if (!_scroll.hasClients ||
        _scroll.position.extentAfter >= 420 ||
        !_canLoadNext ||
        _loadFailed ||
        _loadingMore ||
        view == null ||
        !view.hasMore) {
      return;
    }
    unawaited(_loadMore(view));
  }

  Future<void> _ensureFirstPage() async {
    if (mounted) {
      setState(() {
        _initializing = true;
        _refreshFailed = false;
      });
    }
    try {
      await widget.repository.ensureCollectionPage(
        query: _query,
        view: _view,
        kind: _kind,
        sensitivity: _sensitivity,
        sort: _sort,
        offset: 0,
      );
    } on Object {
      if (mounted) setState(() => _refreshFailed = true);
    } finally {
      if (mounted) setState(() => _initializing = false);
    }
  }

  Future<void> _refreshFirst() async {
    if (_refreshing) return;
    setState(() {
      _refreshing = true;
      _refreshFailed = false;
      _loadFailed = false;
      _completedRequest = null;
    });
    try {
      await widget.repository.refreshCollectionPage(
        query: _query,
        view: _view,
        kind: _kind,
        sensitivity: _sensitivity,
        sort: _sort,
        offset: 0,
      );
    } on Object {
      if (mounted) setState(() => _refreshFailed = true);
      // The last acquired owner projection stays visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _loadMore(_DocumentsView view) async {
    final requestKey =
        '$_query|$_view|$_kind|$_sensitivity|$_sort:${view.nextOffset}';
    if (_loadingMore ||
        _loadFailed ||
        !_canLoadNext ||
        !view.hasMore ||
        _completedRequest == requestKey) {
      return;
    }
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshCollectionPage(
        query: _query,
        view: _view,
        kind: _kind,
        sensitivity: _sensitivity,
        sort: _sort,
        offset: view.nextOffset,
      );
      final source = await widget.repository.readCollectionSource(
        query: _query,
        view: _view,
        kind: _kind,
        sensitivity: _sensitivity,
        sort: _sort,
        offset: view.nextOffset,
      );
      final received = await widget.repository.readCollectionPage(
        query: _query,
        view: _view,
        kind: _kind,
        sensitivity: _sensitivity,
        sort: _sort,
        offset: view.nextOffset,
      );
      if (source.invalidated ||
          source.lastErrorCode != null ||
          source.lastSuccessAt == null ||
          received == null) {
        throw StateError('Document continuation unavailable');
      }
      if (!mounted) return;
      _completedRequest = requestKey;
    } on Object {
      if (mounted) setState(() => _loadFailed = true);
    } finally {
      if (mounted) {
        setState(() => _loadingMore = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _checkEnd();
        });
      }
    }
  }

  void _setScope({
    String? query,
    String? view,
    String? kind,
    String? sensitivity,
    String? sort,
  }) {
    final nextQuery = query ?? _query;
    final nextView = view ?? _view;
    final nextKind = kind ?? _kind;
    final nextSensitivity = sensitivity ?? _sensitivity;
    final nextSort = sort ?? _sort;
    if (nextQuery == _query &&
        nextView == _view &&
        nextKind == _kind &&
        nextSensitivity == _sensitivity &&
        nextSort == _sort) {
      return;
    }
    setState(() {
      _query = nextQuery;
      _view = nextView;
      _kind = nextKind;
      _sensitivity = nextSensitivity;
      _sort = nextSort;
      _completedRequest = null;
      _loadFailed = false;
      _refreshFailed = false;
      _initializing = true;
      _resetSource();
    });
    unawaited(_ensureFirstPage());
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) _setScope(query: value.trim());
    });
  }

  void _openSearch() {
    if (_searching) return;
    setState(() => _searching = true);
  }

  void _closeSearch() {
    _searchDebounce?.cancel();
    if (_search.text.isNotEmpty) _search.clear();
    if (_query.isNotEmpty) {
      _setScope(query: '');
    }
    if (mounted) setState(() => _searching = false);
  }

  Future<void> _showSort() async {
    final value = await showModalBottomSheet<String>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _SortTile(
              label: 'Plus récents',
              value: 'recent',
              selected: _sort == 'recent',
            ),
            _SortTile(
              label: 'Plus anciens',
              value: 'oldest',
              selected: _sort == 'oldest',
            ),
            _SortTile(
              label: 'Nom A–Z',
              value: 'title',
              selected: _sort == 'title',
            ),
            _SortTile(
              label: 'Échéance',
              value: 'expiry',
              selected: _sort == 'expiry',
            ),
          ],
        ),
      ),
    );
    if (value != null && mounted) _setScope(sort: value);
  }

  Future<void> _showFilters(_DocumentsView view) async {
    var kind = _kind;
    var sensitivity = _sensitivity;
    final result = await showModalBottomSheet<_FilterSelection>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Filtres', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: MakoloSpacing.md),
                Text('Type', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: MakoloSpacing.sm),
                Wrap(
                  spacing: MakoloSpacing.sm,
                  runSpacing: MakoloSpacing.sm,
                  children: [
                    ChoiceChip(
                      label: const Text('Tous'),
                      selected: kind.isEmpty,
                      onSelected: (_) => setSheetState(() => kind = ''),
                    ),
                    for (final option in view.kindOptions)
                      ChoiceChip(
                        label: Text(option.label),
                        selected: kind == option.id,
                        onSelected: (_) =>
                            setSheetState(() => kind = option.id),
                      ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.lg),
                Text(
                  'Confidentialité',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: MakoloSpacing.sm),
                Wrap(
                  spacing: MakoloSpacing.sm,
                  runSpacing: MakoloSpacing.sm,
                  children: [
                    ChoiceChip(
                      label: const Text('Toutes'),
                      selected: sensitivity.isEmpty,
                      onSelected: (_) => setSheetState(() => sensitivity = ''),
                    ),
                    for (final option in view.sensitivityOptions)
                      ChoiceChip(
                        label: Text(option.label),
                        selected: sensitivity == option.id,
                        onSelected: (_) =>
                            setSheetState(() => sensitivity = option.id),
                      ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.lg),
                Row(
                  children: [
                    Expanded(
                      child: MakoloActionButton(
                        label: 'Effacer',
                        appearance: MakoloActionAppearance.quiet,
                        onPressed: () => Navigator.of(sheetContext).pop(
                          const _FilterSelection(kind: '', sensitivity: ''),
                        ),
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: MakoloActionButton(
                        label: 'Appliquer',
                        appearance: MakoloActionAppearance.primary,
                        onPressed: () => Navigator.of(sheetContext).pop(
                          _FilterSelection(
                            kind: kind,
                            sensitivity: sensitivity,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (result != null && mounted) {
      _setScope(kind: result.kind, sensitivity: result.sensitivity);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<StoredProjection>>(
      stream: _pages,
      initialData: const [],
      builder: (context, pagesSnapshot) {
        final view = _DocumentsView.fromPages(
          pagesSnapshot.data ?? const [],
          query: _query,
          view: _view,
          kind: _kind,
          sensitivity: _sensitivity,
          sort: _sort,
        );
        return StreamBuilder<ResourceSourceState>(
          stream: _source,
          initialData: ResourceSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final source = sourceSnapshot.data ?? ResourceSourceState.unknown;
            _visibleView = view;
            _canLoadNext =
                source.lastSuccessAt != null &&
                !source.invalidated &&
                source.reachability != ReachabilityState.unreachable;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) _checkEnd();
            });

            final filterBar = Row(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _ViewChip(
                          label: 'Tous',
                          selected: _view == 'current',
                          onSelected: () => _setScope(view: 'current'),
                        ),
                        const SizedBox(width: MakoloSpacing.sm),
                        _ViewChip(
                          label: 'À échéance',
                          selected: _view == 'expiring',
                          onSelected: () => _setScope(view: 'expiring'),
                        ),
                        const SizedBox(width: MakoloSpacing.sm),
                        _ViewChip(
                          label: 'Archivés',
                          selected: _view == 'archived',
                          onSelected: () => _setScope(view: 'archived'),
                        ),
                        const SizedBox(width: MakoloSpacing.md),
                      ],
                    ),
                  ),
                ),
                MakoloIconActionButton(
                  tooltip: 'Filtrer',
                  icon: Icons.tune_rounded,
                  onPressed: () => _showFilters(view),
                ),
                MakoloIconActionButton(
                  tooltip: 'Trier',
                  icon: Icons.swap_vert_rounded,
                  onPressed: _showSort,
                ),
              ],
            );

            final children = <Widget>[
              if (view.hasSnapshot &&
                  (source.reachability == ReachabilityState.unreachable ||
                      _refreshFailed))
                const _ResourceContinuityNotice(
                  message:
                      'Données enregistrées sur cet appareil. '
                      'Mise à jour indisponible.',
                ),
              if (!view.hasSnapshot && _initializing)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
                  child: Center(
                    child: CircularProgressIndicator.adaptive(),
                  ),
                )
              else if (!view.hasSnapshot &&
                  (_refreshFailed ||
                      source.invalidated ||
                      source.reachability == ReachabilityState.unreachable))
                _ResourceUnavailable(
                  ownerDenied: source.ownerDenied,
                  onRetry: _refreshFirst,
                )
              else if (view.items.isEmpty)
                _EmptyDocuments(
                  query: _query,
                  archived: _view == 'archived',
                  onAdd: _view == 'archived' ? null : widget.onAddDocument,
                )
              else
                for (final item in view.items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: _DocumentCard(
                      item: item,
                      onTap: () => widget.onOpenDocument(item.id),
                    ),
                  ),
              if (_loadingMore && view.hasMore)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(MakoloSpacing.md),
                    child: CircularProgressIndicator.adaptive(),
                  ),
                ),
              if (_loadFailed && view.hasMore)
                Center(
                  child: MakoloActionButton(
                    label: 'Réessayer',
                    appearance: MakoloActionAppearance.quiet,
                    onPressed: () {
                      setState(() => _loadFailed = false);
                      unawaited(_loadMore(view));
                    },
                  ),
                ),
            ];

            return ResourceCollectionScaffold(
              title: 'Mes documents',
              count: view.total,
              searching: _searching,
              searchController: _search,
              searchHint: 'Rechercher dans mes documents',
              onSearchChanged: _onSearchChanged,
              onOpenSearch: _openSearch,
              onCloseSearch: _closeSearch,
              onRefresh: _refreshFirst,
              refreshing: _refreshing,
              actions: [
                MakoloIconActionButton(
                  tooltip: 'Ajouter',
                  icon: Icons.add_rounded,
                  onPressed: widget.onAddDocument,
                ),
              ],
              filterBar: filterBar,
              scrollController: _scroll,
              storageKey: PageStorageKey<String>(
                'documents:$_query:$_view:$_kind:$_sensitivity:$_sort',
              ),
              children: children,
            );
          },
        );
      },
    );
  }

class _ResourceContinuityNotice extends StatelessWidget {
  const _ResourceContinuityNotice({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.cloud_off_outlined,
            size: 18,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: MakoloSpacing.xs),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _ResourceUnavailable extends StatelessWidget {
  const _ResourceUnavailable({
    required this.ownerDenied,
    required this.onRetry,
  });

  final bool ownerDenied;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
    child: Column(
      children: [
        const Icon(Icons.cloud_off_outlined, size: 40),
        const SizedBox(height: MakoloSpacing.sm),
        Text(
          ownerDenied
              ? 'Ces documents ne sont plus disponibles.'
              : 'Impossible d’actualiser vos documents.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: MakoloSpacing.md),
        MakoloActionButton(
          label: 'Réessayer',
          appearance: MakoloActionAppearance.quiet,
          onPressed: onRetry,
        ),
      ],
    ),
  );
}

class _ViewChip extends StatelessWidget {
  const _ViewChip({
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final bool selected;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) => ChoiceChip(
    label: Text(label),
    selected: selected,
    visualDensity: VisualDensity.compact,
    labelPadding: const EdgeInsets.symmetric(horizontal: 6),
    onSelected: (_) => onSelected(),
  );
}

class _SortTile extends StatelessWidget {
  const _SortTile({
    required this.label,
    required this.value,
    required this.selected,
  });

  final String label;
  final String value;
  final bool selected;

  @override
  Widget build(BuildContext context) => ListTile(
    title: Text(label),
    trailing: selected ? const Icon(Icons.check_rounded) : null,
    onTap: () => Navigator.of(context).pop(value),
  );
}

class _FilterSelection {
  const _FilterSelection({required this.kind, required this.sensitivity});

  final String kind;
  final String sensitivity;
}

class _EmptyDocuments extends StatelessWidget {
  const _EmptyDocuments({
    required this.query,
    required this.archived,
    required this.onAdd,
  });

  final String query;
  final bool archived;
  final VoidCallback? onAdd;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
    child: Column(
      children: [
        Icon(
          query.isNotEmpty ? Icons.search_off_rounded : Icons.folder_outlined,
          size: 40,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
        const SizedBox(height: MakoloSpacing.sm),
        Text(
          query.isNotEmpty
              ? 'Aucun résultat'
              : archived
              ? 'Aucun document archivé'
              : 'Aucun document',
        ),
        if (onAdd != null && query.isEmpty) ...[
          const SizedBox(height: MakoloSpacing.md),
          MakoloIconActionButton(
            tooltip: 'Ajouter',
            icon: Icons.add_rounded,
            onPressed: onAdd,
          ),
        ],
      ],
    ),
  );
}

class _DocumentCard extends StatelessWidget {
  const _DocumentCard({required this.item, required this.onTap});

  final _DocumentItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => MakoloCard(
    onTap: onTap,
    child: Row(
      children: [
        Icon(
          Icons.description_outlined,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(width: MakoloSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(item.title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: MakoloSpacing.xs),
              Text(
                [
                  item.kindLabel,
                  if (item.validityLabel != null) item.validityLabel!,
                  if (item.archived) 'Archivé',
                ].join(' · '),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        const Icon(Icons.chevron_right_rounded),
      ],
    ),
  );
}

class _DocumentsView {
  const _DocumentsView({
    required this.hasSnapshot,
    required this.items,
    required this.kindOptions,
    required this.sensitivityOptions,
    required this.hasMore,
    required this.nextOffset,
    required this.total,
  });

  final bool hasSnapshot;
  final List<_DocumentItem> items;
  final List<_Option> kindOptions;
  final List<_Option> sensitivityOptions;
  final bool hasMore;
  final int nextOffset;
  final int? total;

  factory _DocumentsView.fromPages(
    List<StoredProjection> pages, {
    required String query,
    required String view,
    required String kind,
    required String sensitivity,
    required String sort,
  }) {
    bool matches(StoredProjection page) {
      if (page.kind != ResourceRepository.collectionProjectionKind) {
        return false;
      }
      final documents = _map(page.payload['documents']);
      final pageQuery = _string(documents['query']) ?? '';
      final pageView = _string(documents['view']) ?? 'current';
      final pageSort = _string(documents['sort']) ?? 'recent';
      final filters = _map(documents['filters']);
      final pageKind = _string(filters['kind']) ?? '';
      final pageSensitivity = _string(filters['sensitivity']) ?? '';
      return pageQuery == query &&
          pageView == view &&
          pageSort == sort &&
          pageKind == kind &&
          pageSensitivity == sensitivity;
    }

    final selected = pages.where(matches).toList()
      ..sort((a, b) => _offset(a).compareTo(_offset(b)));

    var localSearch = false;
    if (selected.isEmpty &&
        query.isNotEmpty &&
        view == 'current' &&
        kind.isEmpty &&
        sensitivity.isEmpty &&
        sort == 'recent') {
      localSearch = true;
      selected.addAll(
        pages.where((page) {
          if (page.kind != ResourceRepository.collectionProjectionKind) {
            return false;
          }
          final documents = _map(page.payload['documents']);
          final filters = _map(documents['filters']);
          return (_string(documents['query']) ?? '').isEmpty &&
              (_string(documents['view']) ?? 'current') == 'current' &&
              (_string(documents['sort']) ?? 'recent') == 'recent' &&
              (_string(filters['kind']) ?? '').isEmpty &&
              (_string(filters['sensitivity']) ?? '').isEmpty;
        }),
      );
      selected.sort((a, b) => _offset(a).compareTo(_offset(b)));
    }

    if (selected.isEmpty) {
      return const _DocumentsView(
        hasSnapshot: false,
        items: [],
        kindOptions: [],
        sensitivityOptions: [],
        hasMore: false,
        nextOffset: 0,
        total: null,
      );
    }

    final items = <_DocumentItem>[];
    final seen = <String>{};
    for (final page in selected) {
      final rows = _map(page.payload['documents'])['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final row = _map(raw);
        final id = _string(row['id']);
        final title = _string(row['title']);
        if (id == null || title == null || !seen.add(id)) continue;
        final current = _map(row['current_version']);
        final validity = _map(current['validity']);
        items.add(
          _DocumentItem(
            id: id,
            title: title,
            kindLabel: _string(row['asset_kind_label']) ?? 'Document',
            kind: _string(row['asset_kind']) ?? '',
            sensitivity: _string(row['sensitivity']) ?? '',
            validityLabel: _validity(validity),
            archived: _string(row['status']) == 'archived',
          ),
        );
      }
    }

    final firstDocuments = _map(selected.first.payload['documents']);
    final options = _map(firstDocuments['filter_options']);
    final kindOptions = _options(options['kinds']);
    final sensitivityOptions = _options(options['sensitivities']);
    final lastDocuments = _map(selected.last.payload['documents']);
    final page = _map(lastDocuments['page']);
    final offset = _int(page['offset']) ?? _offset(selected.last);
    final limit = _int(page['limit']) ?? ResourceRepository.defaultLimit;
    final needle = query.toLowerCase();
    final visibleItems = localSearch
        ? items
              .where((item) => item.title.toLowerCase().contains(needle))
              .toList(growable: false)
        : items;

    return _DocumentsView(
      hasSnapshot: true,
      items: List.unmodifiable(visibleItems),
      kindOptions: List.unmodifiable(kindOptions),
      sensitivityOptions: List.unmodifiable(sensitivityOptions),
      hasMore: localSearch
          ? false
          : page['has_more'] == true || lastDocuments['has_more'] == true,
      nextOffset: localSearch ? 0 : offset + limit,
      total: localSearch ? visibleItems.length : _int(firstDocuments['count']),
    );
  }

  static int _offset(StoredProjection projection) {
    final documents = _map(projection.payload['documents']);
    return _int(_map(documents['page'])['offset']) ?? 0;
  }
}

class _DocumentItem {
  const _DocumentItem({
    required this.id,
    required this.title,
    required this.kindLabel,
    required this.kind,
    required this.sensitivity,
    required this.validityLabel,
    required this.archived,
  });

  final String id;
  final String title;
  final String kindLabel;
  final String kind;
  final String sensitivity;
  final String? validityLabel;
  final bool archived;
}

class _Option {
  const _Option({required this.id, required this.label});

  final String id;
  final String label;
}

List<_Option> _options(Object? raw) {
  if (raw is! List) return const [];
  final result = <_Option>[];
  for (final value in raw) {
    final row = _map(value);
    final id = _string(row['id']);
    final label = _string(row['label']);
    if (id != null && label != null) {
      result.add(_Option(id: id, label: label));
    }
  }
  return result;
}

String? _validity(Map<String, dynamic> value) {
  final state = _string(value['state']);
  final expires = _displayIsoDate(_string(value['expires_at']));
  return switch (state) {
    'expired' when expires != null => 'Expiré · $expires',
    'expired' => 'Expiré',
    'not_yet_issued' => 'À venir',
    'current' when expires != null => 'Jusqu’au $expires',
    _ => null,
  };
}

String? _displayIsoDate(String? value) {
  if (value == null) return null;
  final date = DateTime.tryParse(value);
  if (date == null) return value;
  final day = date.day.toString().padLeft(2, '0');
  final month = date.month.toString().padLeft(2, '0');
  return '$day/$month/${date.year}';
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

int? _int(Object? value) =>
    value is num ? value.toInt() : int.tryParse('$value');
