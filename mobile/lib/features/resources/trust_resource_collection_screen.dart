import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../sync/freshness.dart';
import 'trust_resource_repository.dart';

class TrustResourceCollectionScreen extends StatefulWidget {
  const TrustResourceCollectionScreen({
    super.key,
    required this.family,
    required this.repository,
    required this.onOpenItem,
  });

  final TrustResourceFamily family;
  final TrustResourceRepository repository;
  final ValueChanged<String> onOpenItem;

  @override
  State<TrustResourceCollectionScreen> createState() =>
      _TrustResourceCollectionScreenState();
}

class _TrustResourceCollectionScreenState
    extends State<TrustResourceCollectionScreen> {
  final _search = TextEditingController();
  final _scroll = ScrollController();
  Timer? _searchDebounce;

  String _query = '';
  String _status = 'all';
  String _type = '';
  String _sort = 'recent';

  bool _initializing = true;
  bool _refreshing = false;
  bool _refreshFailed = false;
  bool _loadingMore = false;
  bool _loadFailed = false;
  bool _canLoadNext = false;
  String? _completedRequest;
  _TrustCollectionView? _visibleView;
  late Stream<List<StoredProjection>> _pages;
  late Stream<TrustResourceSourceState> _source;

  String get _title =>
      widget.family == TrustResourceFamily.proofs ? 'Mes preuves' : 'Mes titres';

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_checkEnd);
    _bind();
    unawaited(_ensureFirstPage());
  }

  @override
  void didUpdateWidget(covariant TrustResourceCollectionScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.family != widget.family) {
      _query = '';
      _status = 'all';
      _type = '';
      _sort = 'recent';
      _search.clear();
      _bind();
      unawaited(_ensureFirstPage());
    }
  }

  void _bind() {
    _pages = widget.repository.watchCollectionPages(widget.family);
    _resetSource();
  }

  void _resetSource() {
    _source = widget.repository.watchCollectionSource(
      family: widget.family,
      query: _query,
      status: _status,
      type: _type,
      sort: _sort,
    );
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _search.dispose();
    _scroll.dispose();
    super.dispose();
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
        family: widget.family,
        query: _query,
        status: _status,
        type: _type,
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
        family: widget.family,
        query: _query,
        status: _status,
        type: _type,
        sort: _sort,
        offset: 0,
      );
    } on Object {
      // Keep the last acquired Trust projection visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
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

  Future<void> _loadMore(_TrustCollectionView view) async {
    final requestKey =
        '${widget.family.name}|$_query|$_status|$_type|$_sort:${view.nextOffset}';
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
        family: widget.family,
        query: _query,
        status: _status,
        type: _type,
        sort: _sort,
        offset: view.nextOffset,
      );
      final source = await widget.repository.readCollectionSource(
        family: widget.family,
        query: _query,
        status: _status,
        type: _type,
        sort: _sort,
        offset: view.nextOffset,
      );
      final received = await widget.repository.readCollectionPage(
        family: widget.family,
        query: _query,
        status: _status,
        type: _type,
        sort: _sort,
        offset: view.nextOffset,
      );
      if (source.invalidated ||
          source.lastErrorCode != null ||
          source.lastSuccessAt == null ||
          received == null) {
        throw StateError('Trust continuation unavailable');
      }
      if (mounted) _completedRequest = requestKey;
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
    String? status,
    String? type,
    String? sort,
  }) {
    final nextQuery = query ?? _query;
    final nextStatus = status ?? _status;
    final nextType = type ?? _type;
    final nextSort = sort ?? _sort;
    if (nextQuery == _query &&
        nextStatus == _status &&
        nextType == _type &&
        nextSort == _sort) {
      return;
    }
    setState(() {
      _query = nextQuery;
      _status = nextStatus;
      _type = nextType;
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
    _searchDebounce = Timer(
      const Duration(milliseconds: 350),
      () {
        if (mounted) _setScope(query: value.trim());
      },
    );
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
              label: widget.family == TrustResourceFamily.proofs
                  ? 'Type A–Z'
                  : 'Titre A–Z',
              value: 'title',
              selected: _sort == 'title',
            ),
          ],
        ),
      ),
    );
    if (value != null && mounted) _setScope(sort: value);
  }

  Future<void> _showTypeFilter(_TrustCollectionView view) async {
    var selected = _type;
    final value = await showModalBottomSheet<String>(
      context: context,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Type', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: MakoloSpacing.md),
                Wrap(
                  spacing: MakoloSpacing.sm,
                  runSpacing: MakoloSpacing.sm,
                  children: [
                    ChoiceChip(
                      label: const Text('Tous'),
                      selected: selected.isEmpty,
                      onSelected: (_) => setSheetState(() => selected = ''),
                    ),
                    for (final option in view.typeOptions)
                      ChoiceChip(
                        label: Text(option.label),
                        selected: selected == option.id,
                        onSelected: (_) =>
                            setSheetState(() => selected = option.id),
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
                        onPressed: () => Navigator.of(sheetContext).pop(''),
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: MakoloActionButton(
                        label: 'Appliquer',
                        appearance: MakoloActionAppearance.primary,
                        onPressed: () =>
                            Navigator.of(sheetContext).pop(selected),
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
    if (value != null && mounted) _setScope(type: value);
  }

  List<Widget> _statusChips() {
    final values = widget.family == TrustResourceFamily.proofs
        ? const [
            ('all', 'Toutes'),
            ('active', 'Actives'),
            ('revoked', 'Révoquées'),
          ]
        : const [
            ('all', 'Tous'),
            ('issued', 'Valides'),
            ('revoked', 'Révoqués'),
          ];
    return [
      for (final value in values)
        Padding(
          padding: const EdgeInsets.only(right: MakoloSpacing.sm),
          child: ChoiceChip(
            label: Text(value.$2),
            selected: _status == value.$1,
            onSelected: (_) => _setScope(status: value.$1),
          ),
        ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_title),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Actualiser',
            icon: Icons.refresh_rounded,
            onPressed: _refreshing ? null : _refreshFirst,
          ),
        ],
      ),
      body: StreamBuilder<List<StoredProjection>>(
        stream: _pages,
        initialData: const [],
        builder: (context, pagesSnapshot) {
          final view = _TrustCollectionView.fromPages(
            pagesSnapshot.data ?? const [],
            family: widget.family,
            query: _query,
            status: _status,
            type: _type,
            sort: _sort,
          );
          return StreamBuilder<TrustResourceSourceState>(
            stream: _source,
            initialData: TrustResourceSourceState.unknown,
            builder: (context, sourceSnapshot) {
              final source =
                  sourceSnapshot.data ?? TrustResourceSourceState.unknown;
              _visibleView = view;
              _canLoadNext =
                  source.lastSuccessAt != null &&
                  !source.invalidated &&
                  source.reachability != ReachabilityState.unreachable;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) _checkEnd();
              });

              return RefreshIndicator(
                onRefresh: _refreshFirst,
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 860),
                    child: ListView(
                  controller: _scroll,
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  children: [
                    TextField(
                      controller: _search,
                      onChanged: _onSearchChanged,
                      textInputAction: TextInputAction.search,
                      decoration: const InputDecoration(
                        hintText: 'Rechercher',
                        prefixIcon: Icon(Icons.search_rounded),
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(children: _statusChips()),
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Row(
                      children: [
                        if (view.total != null && view.total! > 0)
                          Text(
                            '${view.total}',
                            style: Theme.of(context).textTheme.labelLarge
                                ?.copyWith(
                                  color: Theme.of(context).colorScheme.primary,
                                ),
                          ),
                        const Spacer(),
                        MakoloIconActionButton(
                          tooltip: 'Filtrer',
                          icon: Icons.tune_rounded,
                          onPressed: () => _showTypeFilter(view),
                        ),
                        MakoloIconActionButton(
                          tooltip: 'Trier',
                          icon: Icons.swap_vert_rounded,
                          onPressed: _showSort,
                        ),
                      ],
                    ),
                    if (view.hasSnapshot &&
                        (source.reachability == ReachabilityState.unreachable ||
                            _refreshFailed))
                      const _TrustContinuityNotice(),
                    if (!view.hasSnapshot && _initializing)
                      const Padding(
                        padding: EdgeInsets.symmetric(
                          vertical: MakoloSpacing.xl,
                        ),
                        child: Center(
                          child: CircularProgressIndicator.adaptive(),
                        ),
                      )
                    else if (!view.hasSnapshot &&
                        (_refreshFailed ||
                            source.invalidated ||
                            source.reachability == ReachabilityState.unreachable))
                      _TrustUnavailable(
                        family: widget.family,
                        ownerDenied: source.ownerDenied,
                        onRetry: _refreshFirst,
                      )
                    else if (view.items.isEmpty)
                      _EmptyTrustCollection(
                        family: widget.family,
                        query: _query,
                      )
                    else
                      for (final item in view.items)
                        Padding(
                          padding: const EdgeInsets.only(
                            bottom: MakoloSpacing.sm,
                          ),
                          child: _TrustResourceCard(
                            family: widget.family,
                            item: item,
                            onTap: () => widget.onOpenItem(item.id),
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
                  ],
                    ),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _TrustContinuityNotice extends StatelessWidget {
  const _TrustContinuityNotice();

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
              'Données enregistrées sur cet appareil. '
              'Mise à jour indisponible.',
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

class _TrustUnavailable extends StatelessWidget {
  const _TrustUnavailable({
    required this.family,
    required this.ownerDenied,
    required this.onRetry,
  });

  final TrustResourceFamily family;
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
              ? family == TrustResourceFamily.proofs
                  ? 'Ces preuves ne sont plus disponibles.'
                  : 'Ces titres ne sont plus disponibles.'
              : family == TrustResourceFamily.proofs
                  ? 'Impossible d’actualiser vos preuves.'
                  : 'Impossible d’actualiser vos titres.',
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

class _EmptyTrustCollection extends StatelessWidget {
  const _EmptyTrustCollection({required this.family, required this.query});

  final TrustResourceFamily family;
  final String query;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
    child: Column(
      children: [
        Icon(
          query.isEmpty
              ? family == TrustResourceFamily.proofs
                    ? Icons.verified_outlined
                    : Icons.workspace_premium_outlined
              : Icons.search_off_rounded,
          size: 40,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
        const SizedBox(height: MakoloSpacing.sm),
        Text(
          query.isNotEmpty
              ? 'Aucun résultat'
              : family == TrustResourceFamily.proofs
              ? 'Aucune preuve'
              : 'Aucun titre',
        ),
      ],
    ),
  );
}

class _TrustResourceCard extends StatelessWidget {
  const _TrustResourceCard({
    required this.family,
    required this.item,
    required this.onTap,
  });

  final TrustResourceFamily family;
  final _TrustItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => MakoloCard(
    onTap: onTap,
    child: Row(
      children: [
        Icon(
          family == TrustResourceFamily.proofs
              ? Icons.verified_outlined
              : Icons.workspace_premium_outlined,
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
                [item.context, item.statusLabel, item.date]
                    .whereType<String>()
                    .where((value) => value.isNotEmpty)
                    .join(' · '),
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

class _TrustCollectionView {
  const _TrustCollectionView({
    required this.hasSnapshot,
    required this.items,
    required this.typeOptions,
    required this.hasMore,
    required this.nextOffset,
    required this.total,
  });

  final bool hasSnapshot;
  final List<_TrustItem> items;
  final List<_TrustOption> typeOptions;
  final bool hasMore;
  final int nextOffset;
  final int? total;

  factory _TrustCollectionView.fromPages(
    List<StoredProjection> pages, {
    required TrustResourceFamily family,
    required String query,
    required String status,
    required String type,
    required String sort,
  }) {
    bool matches(StoredProjection page) {
      if (page.kind != family.collectionProjection) return false;
      final payload = page.payload;
      return (_string(payload['query']) ?? '') == query &&
          (_string(payload['status']) ?? 'all') == status &&
          (_string(
                    payload[
                        family == TrustResourceFamily.proofs
                            ? 'proof_type'
                            : 'credential_type'],
                  ) ??
                  '') ==
              type &&
          (_string(payload['sort']) ?? 'recent') == sort;
    }

    final selected = pages.where(matches).toList()
      ..sort((a, b) => _offset(a).compareTo(_offset(b)));

    var localSearch = false;
    if (selected.isEmpty &&
        query.isNotEmpty &&
        status == 'all' &&
        type.isEmpty &&
        sort == 'recent') {
      localSearch = true;
      selected.addAll(
        pages.where((page) {
          if (page.kind != family.collectionProjection) return false;
          final payload = page.payload;
          return (_string(payload['query']) ?? '').isEmpty &&
              (_string(payload['status']) ?? 'all') == 'all' &&
              (_string(
                        payload[
                            family == TrustResourceFamily.proofs
                                ? 'proof_type'
                                : 'credential_type'],
                      ) ??
                      '')
                  .isEmpty &&
              (_string(payload['sort']) ?? 'recent') == 'recent';
        }),
      );
      selected.sort((a, b) => _offset(a).compareTo(_offset(b)));
    }

    if (selected.isEmpty) {
      return const _TrustCollectionView(
        hasSnapshot: false,
        items: [],
        typeOptions: [],
        hasMore: false,
        nextOffset: 0,
        total: null,
      );
    }

    final items = <_TrustItem>[];
    final seen = <String>{};
    for (final page in selected) {
      final rows = page.payload['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final row = _map(raw);
        final id = _string(row['id']);
        if (id == null || !seen.add(id)) continue;
        final activity = _map(row['activity']);
        final issuer = _map(row['issuer']);
        final title = family == TrustResourceFamily.proofs
            ? _string(row['proof_type_label'])
            : _string(row['title']);
        if (title == null) continue;
        items.add(
          _TrustItem(
            id: id,
            title: title,
            context: family == TrustResourceFamily.proofs
                ? _string(activity['title'])
                : _string(issuer['name']) ?? _string(activity['title']),
            searchText: [
              title,
              _string(activity['title']),
              _string(issuer['name']),
              _string(row['proof_type_label']),
              _string(row['credential_type_label']),
              _string(row['status_label']),
            ].whereType<String>().join(' ').casefold(),
            statusLabel: _string(row['status_label']),
            date: _displayDate(_string(row['issued_at'])),
          ),
        );
      }
    }

    final filterOptions = _map(selected.first.payload['filter_options']);
    final typeOptions = _options(filterOptions['types']);
    final page = _map(selected.last.payload['page']);
    final offset = _int(page['offset']) ?? _offset(selected.last);
    final limit = _int(page['limit']) ?? TrustResourceRepository.defaultLimit;
    final needle = query.casefold();
    final visible = localSearch
        ? items
              .where(
                (item) => item.searchText.contains(needle),
              )
              .toList(growable: false)
        : items;

    return _TrustCollectionView(
      hasSnapshot: true,
      items: List.unmodifiable(visible),
      typeOptions: List.unmodifiable(typeOptions),
      hasMore: localSearch ? false : page['has_more'] == true,
      nextOffset: localSearch ? 0 : offset + limit,
      total: localSearch ? visible.length : _int(selected.first.payload['count']),
    );
  }

  static int _offset(StoredProjection projection) =>
      _int(_map(projection.payload['page'])['offset']) ?? 0;
}

class _TrustItem {
  const _TrustItem({
    required this.id,
    required this.title,
    required this.context,
    required this.searchText,
    required this.statusLabel,
    required this.date,
  });

  final String id;
  final String title;
  final String? context;
  final String searchText;
  final String? statusLabel;
  final String? date;
}

class _TrustOption {
  const _TrustOption({required this.id, required this.label});

  final String id;
  final String label;
}

List<_TrustOption> _options(Object? value) {
  if (value is! List) return const [];
  final options = <_TrustOption>[];
  for (final raw in value) {
    final row = _map(raw);
    final id = _string(row['id']);
    final label = _string(row['label']);
    if (id != null && label != null) {
      options.add(_TrustOption(id: id, label: label));
    }
  }
  return options;
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

int? _int(Object? value) => value is num ? value.toInt() : int.tryParse('$value');

String? _displayDate(String? value) {
  if (value == null) return null;
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  final local = parsed.toLocal();
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  return '$day/$month/${local.year}';
}

extension on String {
  String casefold() => toLowerCase();
}
