import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../platform/preferences/secure_string_preferences.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';

import '../../data/local/profile_store.dart';
import '../../navigation/destination.dart';
import '../../network/makolo_api_client.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/sync_status.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/freshness.dart';
import 'me_selector.dart';
import 'me_collectives_content.dart';

/// Owner-backed personal collective relationships, not an authority editor.
class MeCollectivesScreen extends StatefulWidget {
  const MeCollectivesScreen({
    super.key,
    required this.personal,
    required this.api,
    required this.onOpenDestination,
    this.onActSpace,
  });

  final PersonalRepository personal;
  final MakoloApiClient api;
  final bool Function(StructuredDestination destination) onOpenDestination;
  final ValueChanged<MeItemPresentation>? onActSpace;

  @override
  State<MeCollectivesScreen> createState() => _MeCollectivesScreenState();
}

class _MeCollectivesScreenState extends State<MeCollectivesScreen> {
  static const _preferences = SecureStringPreferences();
  MeCollectivesLayout _layout = MeCollectivesLayout.categories;
  String get _layoutKey =>
      'me.collectives.layout.${widget.personal.store.profileId}';

  Future<void> _restoreLayout() async {
    final key = _layoutKey;
    try {
      final value = await _preferences.read(key: key);
      if (!mounted || key != _layoutKey) return;
      setState(() {
        _layout = value == 'list'
            ? MeCollectivesLayout.list
            : MeCollectivesLayout.categories;
      });
    } on Object {
      // A device preference is never required for this local-first view.
    }
  }

  void _chooseLayout(MeCollectivesLayout layout) {
    if (_layout == layout) return;
    setState(() => _layout = layout);
    final key = _layoutKey;
    unawaited(_saveLayout(key, layout));
  }

  Future<void> _saveLayout(String key, MeCollectivesLayout layout) async {
    try {
      await _preferences.write(
        key: key,
        value: layout == MeCollectivesLayout.list ? 'list' : 'categories',
      );
    } on Object {
      // Keep the chosen view available even when preferences cannot persist.
    }
  }

  final ScrollController _scroll = ScrollController();
  final TextEditingController _search = TextEditingController();
  bool _searching = false;
  bool _alphabetical = false;
  bool _descending = false;
  late Stream<StoredProjection?> _snapshots;
  StreamSubscription<OwnerSourceState>? _ownerSubscription;
  bool _invalidated = false;
  bool _unreachable = false;
  bool _loading = false;
  bool _failed = false;
  bool _hasMore = false;
  bool _offline = false;
  String? _lastRequested;

  @override
  void initState() {
    super.initState();
    _snapshots = widget.personal.watchMe();
    unawaited(_restoreLayout());
    _bindOwner();
    _scroll.addListener(_checkEnd);
  }

  @override
  void didUpdateWidget(covariant MeCollectivesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.personal != widget.personal) {
      unawaited(_ownerSubscription?.cancel());
      _snapshots = widget.personal.watchMe();
      _invalidated = false;
      _unreachable = false;
      _bindOwner();
      _lastRequested = null;
      _loading = false;
      _failed = false;
      _hasMore = false;
      _search.clear();
      _searching = false;
      _alphabetical = false;
      _descending = false;
      _layout = MeCollectivesLayout.categories;
      unawaited(_restoreLayout());
    }
  }

  @override
  void dispose() {
    unawaited(_ownerSubscription?.cancel());
    _scroll.dispose();
    _search.dispose();
    super.dispose();
  }

  void _bindOwner() {
    _ownerSubscription = widget.personal.watchMeSource().listen((source) {
      if (!mounted) return;
      setState(() {
        _invalidated = source.invalidated;
        _unreachable = source.reachability == ReachabilityState.unreachable;
      });
    });
  }

  void _checkEnd() {
    if (!_scroll.hasClients ||
        _scroll.position.extentAfter >= 480 ||
        !_hasMore ||
        _offline ||
        _search.text.trim().isNotEmpty ||
        _loading ||
        _failed) {
      return;
    }
    unawaited(_loadNext());
  }

  String _progress(StoredProjection projection) {
    final raw = projection.payload['collectives'];
    if (raw is! Map) return '';
    final offsets = <Object?>[
      for (final family in ['authorized_spaces', 'teams', 'groups'])
        (raw[family] is Map ? (raw[family] as Map)['next_offset'] : null),
    ];
    return '${projection.sourceGeneratedAt?.toIso8601String()}:${offsets.join('/')}';
  }

  Future<void> _loadNext() async {
    if (_loading || _failed || _offline || !_hasMore) return;
    final personal = widget.personal;
    StoredProjection? current;
    try {
      current = await personal.store.readProjection('personal.me');
    } on Object {
      if (mounted && personal == widget.personal) {
        setState(() => _failed = true);
      }
      return;
    }
    if (!mounted || current == null || personal != widget.personal) return;
    final progress = _progress(current);
    if (_lastRequested == progress) return;
    _lastRequested = progress;
    setState(() => _loading = true);
    try {
      await personal.loadMoreMe(
        api: widget.api,
        current: current,
        territory: 'collectives',
      );
      if (!mounted || personal != widget.personal) return;
      setState(() => _failed = false);
    } on Object {
      if (!mounted || personal != widget.personal) return;
      _lastRequested = null;
      setState(() => _failed = true);
    } finally {
      if (mounted && personal == widget.personal) {
        setState(() => _loading = false);
      }
    }
  }

  void _retry() {
    setState(() {
      _failed = false;
      _lastRequested = null;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _checkEnd();
    });
  }

  void _toggleSearch() {
    setState(() {
      _searching = !_searching;
      if (!_searching) _search.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    _offline =
        _unreachable ||
        SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
    final scheme = Theme.of(context).colorScheme;
    return StreamBuilder<StoredProjection?>(
      key: ValueKey<String>(
        'me-collectives-scope-${widget.personal.store.profileId}',
      ),
      stream: _snapshots,
      builder: (context, snapshot) {
        final projection = _invalidated ? null : snapshot.data;
        final count = projection == null
            ? null
            : meCollectiveTotal(projection.payload['collectives']);
        return Scaffold(
          backgroundColor: scheme.surfaceContainerLow,
          appBar: AppBar(
            backgroundColor: scheme.surface,
            surfaceTintColor: Colors.transparent,
            leading: IconButton(
              key: const Key('me-collectives-back'),
              tooltip: 'Retour à Moi',
              onPressed: () {
                if (context.canPop()) {
                  context.pop();
                } else {
                  context.go('/me');
                }
              },
              icon: const Icon(Icons.arrow_back_rounded),
            ),
            titleSpacing: 0,
            title: _searching
                ? TextField(
                    key: const Key('me-collectives-search'),
                    controller: _search,
                    autofocus: true,
                    onChanged: (_) => setState(() {}),
                    textInputAction: TextInputAction.search,
                    decoration: const InputDecoration(
                      hintText: 'Rechercher',
                      border: InputBorder.none,
                    ),
                  )
                : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Flexible(
                        child: Text(
                          'Mes collectifs',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (count != null && count > 0) ...[
                        const SizedBox(width: 8),
                        Text(
                          '$count',
                          key: const Key('me-collectives-title-count'),
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(color: scheme.onSurfaceVariant),
                        ),
                      ],
                    ],
                  ),
            actions: [
              IconButton(
                key: const Key('me-collectives-search-toggle'),
                tooltip: _searching
                    ? 'Fermer la recherche'
                    : 'Rechercher un collectif',
                onPressed: _toggleSearch,
                icon: Icon(
                  _searching ? Icons.close_rounded : Icons.search_rounded,
                ),
              ),
              PopupMenuButton<bool>(
                key: const Key('me-collectives-sort'),
                tooltip: 'Trier par ordre alphabétique',
                icon: const Icon(Icons.sort_by_alpha_rounded),
                onSelected: (descending) => setState(() {
                  _alphabetical = true;
                  _descending = descending;
                }),
                itemBuilder: (context) => [
                  CheckedPopupMenuItem<bool>(
                    value: false,
                    checked: _alphabetical && !_descending,
                    child: const Text('Nom A à Z'),
                  ),
                  CheckedPopupMenuItem<bool>(
                    value: true,
                    checked: _alphabetical && _descending,
                    child: const Text('Nom Z à A'),
                  ),
                ],
              ),
              const SizedBox(width: 4),
            ],
          ),
          body: _invalidated
              ? const Center(
                  child: Text('Ces collectifs ne sont plus accessibles.'),
                )
              : projection == null
              ? snapshot.connectionState == ConnectionState.waiting
                    ? const MakoloSkeleton(lines: 3)
                    : const Center(
                        child: Text('Mes collectifs sont indisponibles.'),
                      )
              : _buildCollectives(projection),
        );
      },
    );
  }

  Widget _buildCollectives(StoredProjection projection) {
    final selection = const MeSelector().select(
      projection: projection,
      now: DateTime.now().toUtc(),
    );
    final territory = selection.territories.firstWhere(
      (item) => item.presentation.key == 'collectives',
    );
    _hasMore = territory.hasMore;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _checkEnd();
    });
    return ListView(
      key: PageStorageKey<String>(
        'me-collectives-${widget.personal.store.profileId}',
      ),
      controller: _scroll,
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 36),
      children: [
        MeCollectivesContent(
          key: ValueKey<String>(
            'me-collectives-content-${widget.personal.store.profileId}',
          ),
          items: territory.items,
          collectives: projection.payload['collectives'],
          offline: _offline,
          hasMore: territory.hasMore,
          query: _search.text,
          alphabetical: _alphabetical,
          descending: _descending,
          layout: _layout,
          onLayoutChanged: _chooseLayout,
          mediaApi: widget.api,
          profileId: widget.personal.store.profileId,
          onOpen: widget.onOpenDestination,
          onActSpace: widget.onActSpace,
        ),
        if (_loading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: CircularProgressIndicator.adaptive(),
            ),
          ),
        if (_failed)
          Center(
            child: MakoloActionButton(
              label: 'Réessayer',
              onPressed: _retry,
              appearance: MakoloActionAppearance.quiet,
            ),
          ),
      ],
    );
  }
}
