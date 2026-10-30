import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/possibilities/discovery_possibility_unit.dart';
import '../../presentation/fields/search_filter_bar.dart';
import '../../presentation/fields/geo_autocomplete_field.dart';
import '../../platform/location/geo_search_gateway.dart';
import '../../platform/location/location_capability.dart';
import '../../presentation/search/progressive_search_coordinator.dart';
import '../../platform/maps/map_runtime_config.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_status.dart';
import 'detail_selector.dart';
import 'discovery_mature_view.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';
import 'discovery_wire.dart';

/// A confirmed owner mutation updates the detail snapshot first. Refresh the
/// existing field opportunistically; a failed refresh does not negate a save.
Future<void> _saveDiscoveryPossibility(
  DiscoveryRepository repository,
  DiscoveryItemPresentation item,
  DiscoveryQuery query,
) async {
  final willSave = item.savedState != 'saved';
  if (willSave && !item.canSave) {
    throw StateError('Enregistrement indisponible pour cette possibilité.');
  }
  if (!willSave && !item.canUnsave) {
    throw StateError('Suppression indisponible pour cette possibilité.');
  }
  await repository.setSaved(family: item.family, id: item.id, saved: willSave);
  try {
    await repository.refreshItems(query);
  } on Object {
    // The owner already confirmed the mutation; the snapshot can refresh later.
  }
}

class DiscoveryScreen extends StatefulWidget {
  const DiscoveryScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;

  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

class _DiscoveryScreenState extends State<DiscoveryScreen> {
  static const _selector = DiscoverySelector();
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;
  bool _acquisitionFailed = false;
  bool _loadingMore = false;
  bool _loadMoreFailed = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    try {
      final local = await widget.repository.readItems(_query);
      if (!mounted) return;
      var locallyValid = local != null;
      if (local != null) {
        try {
          DiscoveryWire.validateData(local.payload);
          await widget.repository.indexItemPreviews(_query);
        } on FormatException {
          locallyValid = false;
        }
      }
      final source = await widget.repository.readSource(
        widget.repository.itemsSource(_query),
      );
      if (!mounted) return;
      if (local == null ||
          !locallyValid ||
          DiscoveryRepository.discoveryFreshness.evaluate(
                local,
                now: DateTime.now(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        await _refreshItems();
      }
    } on Object {
      if (mounted) setState(() => _acquisitionFailed = true);
    }
  }

  Future<void> _refreshItems() async {
    if (_refreshing || !mounted) return;
    final current = _query;
    setState(() {
      _refreshing = true;
      _acquisitionFailed = false;
    });
    try {
      final source = await widget.repository.readSource(
        widget.repository.itemsSource(current),
      );
      if (!mounted || !identical(current, _query)) return;
      if (source.lastErrorCode == 'continuation_rejected') {
        setState(() => _query = current.copyWith(page: 1));
      }
      await widget.repository.refreshItems(_query);
    } on Object {
      if (mounted) setState(() => _acquisitionFailed = true);
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  /// Append the server's next lot without navigating away or resetting scroll.
  /// The repository composes the locally stored pages by candidate identity.
  Future<void> _loadNextPage() async {
    if (_loadingMore || _refreshing || !mounted) return;
    final current = _query;
    setState(() => _loadMoreFailed = false);
    try {
      final projection = await widget.repository.readItems(current);
      if (projection == null) throw const FormatException('Missing Discovery field');
      final collection = _selector.collection(projection);
      if (!collection.hasNext) return;
      final token = collection.continuationToken;
      if (token == null || token.isEmpty) {
        throw const FormatException('Missing Discovery continuation');
      }
      if (!mounted || !identical(current, _query)) return;
      setState(() => _loadingMore = true);
      final next = current.copyWith(
        page: current.page + 1,
        continuation: token,
      );
      await widget.repository.refreshItems(next);
      final source = await widget.repository.readSource(
        widget.repository.itemsSource(next),
      );
      if (source.lastErrorCode != null ||
          await widget.repository.readItems(next) == null) {
        throw StateError('Discovery continuation unavailable');
      }
      if (!mounted || !identical(current, _query)) return;
      setState(() => _query = next);
    } on Object {
      if (mounted && identical(current, _query)) {
        setState(() => _loadMoreFailed = true);
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _open(DiscoveryItemPresentation item) {
    // The central owner action may skip N2. Opening the item itself always
    // deepens the same possibility, including Activity-based verticals.
    widget.onOpenItem(item.family, item.id);
  }

  MakoloReachabilityCue _reachability(
    DiscoverySourceState source,
    SyncStatus? syncStatus,
  ) {
    if (syncStatus?.state == SyncVisualState.offline ||
        source.reachability == ReachabilityState.unreachable) {
      return MakoloReachabilityCue.temporarilyUnavailable;
    }
    if (source.lastSuccessAt != null) {
      return MakoloReachabilityCue.reachable;
    }
    return MakoloReachabilityCue.unknown;
  }

  @override
  Widget build(BuildContext context) {
    final source = widget.repository.itemsSource(_query);
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchItems(_query),
      builder: (context, snapshot) {
        return StreamBuilder<DiscoverySourceState>(
          stream: widget.repository.watchSource(source),
          initialData: DiscoverySourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = snapshot.data;
            final sourceState =
                sourceSnapshot.data ?? DiscoverySourceState.unknown;
            final syncStatus = SyncStatusScope.maybeOf(context);
            final serverUnavailable =
                syncStatus?.state != SyncVisualState.offline &&
                const {
                  'timeout',
                  'makolo_unreachable',
                  'secure_connection_failed',
                  'transport_error',
                }.contains(sourceState.lastErrorCode);
            final freshness = projection == null
                ? FreshnessState.fresh
                : DiscoveryRepository.discoveryFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: sourceState.invalidated,
                  );
            final selection = _selector.select(
              projection: projection,
              hasCriteria: _query.hasCriteria,
              freshness: freshness,
              reachability: _reachability(sourceState, syncStatus),
              failure:
                  sourceState.lastErrorCode != null ||
                      snapshot.hasError ||
                      sourceSnapshot.hasError ||
                      _acquisitionFailed
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing,
              serverUnavailable: serverUnavailable,
              sourceErrorCode: sourceState.lastErrorCode,
            );
            return RefreshIndicator(
              onRefresh: _refreshItems,
              child: DiscoveryExplorationView(
                selection: selection,
                onOpen: _open,
                onSave: (item) =>
                    _saveDiscoveryPossibility(widget.repository, item, _query),
                baseUri: widget.repository.api.baseUri,
                shareApi: widget.repository.api,
                onPage: (_) => unawaited(_loadNextPage()),
                autoLoadMore: true,
                loadingMore: _loadingMore,
                loadMoreFailed: _loadMoreFailed,
                onRetry: () => unawaited(_refreshItems()),
              ),
            );
          },
        );
      },
    );
  }
}

class DiscoverySearchScreen extends StatefulWidget {
  const DiscoverySearchScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
    this.location,
    this.geoSearch,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;
  final LocationCapability? location;
  final GeoSearchGateway? geoSearch;

  @override
  State<DiscoverySearchScreen> createState() => _DiscoverySearchScreenState();
}

class _DiscoverySearchScreenState extends State<DiscoverySearchScreen> {
  static const _selector = DiscoverySelector();
  final _search = TextEditingController();
  final _place = TextEditingController();
  GeoSuggestion? _selectedPlace;
  String _when = '';
  String _date = '';
  String _price = '';
  String _vertical = '';
  String? _locationMessage;
  late final ProgressiveSearchCoordinator _searchCoordinator;
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    _searchCoordinator = ProgressiveSearchCoordinator(onSearch: _loadRevision);
  }

  @override
  void dispose() {
    _searchCoordinator.dispose();
    _search.dispose();
    _place.dispose();
    super.dispose();
  }

  void _applyCriteria({bool immediate = true}) {
    _searchChanged(_search.text, immediate: immediate);
  }

  Future<void> _chooseDate() async {
    final today = DateTime.now();
    final chosen = await showDatePicker(
      context: context,
      initialDate: DateTime.tryParse(_date) ?? today,
      firstDate: DateTime(today.year - 1),
      lastDate: DateTime(today.year + 5),
      helpText: 'Choisir une date',
    );
    if (!mounted || chosen == null) return;
    setState(() {
      _when = 'custom';
      _date = '${chosen.year.toString().padLeft(4, '0')}-'
          '${chosen.month.toString().padLeft(2, '0')}-'
          '${chosen.day.toString().padLeft(2, '0')}';
    });
    _applyCriteria();
  }

  void _clearNearby() {
    setState(() {
      _query = _query.copyWith(clearLocation: true, clearContinuation: true);
      _locationMessage = null;
    });
    _applyCriteria();
  }

  Future<void> _toggleNearby() async {
    if (_query.latitude != null) {
      _clearNearby();
      return;
    }
    final location = widget.location;
    if (location == null) {
      setState(() => _locationMessage = 'Position indisponible. La recherche par mots-clés reste possible.');
      return;
    }
    final result = await location.current();
    if (!mounted) return;
    if (!result.available || result.fix == null) {
      setState(() => _locationMessage = 'Position indisponible. La recherche par mots-clés reste possible.');
      return;
    }
    setState(() {
      _query = _query.copyWith(
        latitude: result.fix!.latitude,
        longitude: result.fix!.longitude,
        radiusKm: 25,
        clearContinuation: true,
      );
      _locationMessage = null;
    });
    _applyCriteria();
  }

  // Guest and personal search use the same debounced request scheduler.
  // A newer intent cannot overwrite results or loading state from an older one.
  void _searchChanged(String value, {bool immediate = false}) {
    final query = _query.copyWith(
      text: value.trim(),
      place: _selectedPlace == null
          ? _place.text.trim()
          : _selectedPlace!.label.split(',').first.trim(),
      when: _when == 'custom' ? '' : _when,
      date: _date,
      price: _price,
      vertical: _vertical,
      page: 1,
      clearContinuation: true,
    );
    setState(() {
      _query = query;
      _refreshing = query.hasCriteria;
    });
    if (!query.hasCriteria) {
      _searchCoordinator.invalidate();
      return;
    }
    _searchCoordinator.changed(immediate: immediate);
  }

  void _submit(String value) => _searchChanged(value, immediate: true);

  Future<void> _loadRevision(int revision) async {
    final query = _query;
    if (!query.hasCriteria) return;
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // The owner source records its own failure; keep any matching cache.
    } finally {
      if (mounted && _searchCoordinator.isCurrent(revision)) {
        setState(() => _refreshing = false);
      }
    }
  }

  void _movePage(int page) {
    unawaited(_navigateToPage(page));
  }

  Future<void> _navigateToPage(int page) async {
    if (page < 1) return;
    final current = _query;
    String? token;
    var targetPage = page;
    if (page == current.page + 1) {
      final projection = await widget.repository.readItems(current);
      try {
        if (projection == null) {
          targetPage = 1;
        } else {
          token = _selector.collection(projection).continuationToken;
        }
      } on FormatException {
        targetPage = 1;
      }
    }
    if (!mounted || !identical(current, _query)) return;
    final query = current.copyWith(page: targetPage, continuation: token);
    setState(() => _query = query);
    unawaited(_refreshPage(query));
  }

  Future<void> _refreshPage(DiscoveryQuery query) async {
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // Existing results remain visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _open(DiscoveryItemPresentation item) {
    // The central owner action may skip N2. Opening the item itself always
    // deepens the same possibility, including Activity-based verticals.
    widget.onOpenItem(item.family, item.id);
  }

  void _resetCriteria() {
    _searchCoordinator.invalidate();
    _search.clear();
    _place.clear();
    _selectedPlace = null;
    _when = '';
    _date = '';
    _price = '';
    _vertical = '';
    setState(() {
      _query = const DiscoveryQuery();
      _locationMessage = null;
    });
  }

  MakoloReachabilityCue _reachability(DiscoverySourceState source) {
    if (source.reachability == ReachabilityState.unreachable) {
      return MakoloReachabilityCue.temporarilyUnavailable;
    }
    if (source.lastSuccessAt != null) {
      return MakoloReachabilityCue.reachable;
    }
    return MakoloReachabilityCue.unknown;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Rechercher')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.inner,
              MakoloSpacing.sm,
              MakoloSpacing.inner,
              MakoloSpacing.sm,
            ),
            child: SearchFilterBar(
              filterButtonKey: const Key('discover-search-filter-toggle'),
              filterPanelKey: const Key('discover-search-filter-panel'),
              hasActiveFilters: _place.text.trim().isNotEmpty ||
                  _when.isNotEmpty || _date.isNotEmpty ||
                  _price.isNotEmpty || _query.latitude != null,
              searchField: TextField(
                key: const Key('discover-search-field'),
                controller: _search,
                autofocus: true,
                textInputAction: TextInputAction.search,
                onChanged: _searchChanged,
                onSubmitted: _submit,
                decoration: InputDecoration(
                  hintText: 'Rechercher une possibilité',
                  prefixIcon: const Icon(Icons.search_rounded),
                  border: const OutlineInputBorder(),
                  suffixIcon: _search.text.isEmpty ? null : IconButton(
                    key: const Key('discover-search-clear'),
                    tooltip: 'Effacer la recherche',
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () {
                      _search.clear();
                      _applyCriteria();
                    },
                  ),
                ),
              ),
              filters: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  GeoAutocompleteField(
                    fieldKey: const Key('discover-search-place'),
                    controller: _place,
                    gateway: widget.geoSearch,
                    onSelected: (place) {
                      setState(() => _selectedPlace = place);
                      _applyCriteria();
                    },
                    onEdited: () {
                      _selectedPlace = null;
                      _applyCriteria(immediate: false);
                    },
                    onSubmitted: () => _applyCriteria(),
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  OutlinedButton.icon(
                    key: const Key('discover-search-nearby'),
                    onPressed: _toggleNearby,
                    icon: Icon(_query.latitude == null
                        ? Icons.near_me_outlined
                        : Icons.location_off_outlined),
                    label: Text(_query.latitude == null
                        ? 'Autour de moi · 25 km'
                        : 'Retirer « Autour de moi »'),
                  ),
                  if (_locationMessage != null)
                    Text(_locationMessage!),
                  const SizedBox(height: MakoloSpacing.md),
                  DropdownButtonFormField<String>(
                    key: const Key('discover-search-when'),
                    initialValue: _when,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Quand ?',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.calendar_today_outlined),
                    ),
                    items: const [
                      DropdownMenuItem(value: '', child: Text('Toutes les dates')),
                      DropdownMenuItem(value: 'today', child: Text('Aujourd’hui')),
                      DropdownMenuItem(value: 'tomorrow', child: Text('Demain')),
                      DropdownMenuItem(value: 'weekend', child: Text('Ce week-end')),
                      DropdownMenuItem(value: 'week', child: Text('Cette semaine')),
                      DropdownMenuItem(value: 'custom', child: Text('Choisir une date…')),
                    ],
                    onChanged: (value) {
                      if (value == 'custom') {
                        unawaited(_chooseDate());
                      } else {
                        setState(() {
                          _when = value ?? '';
                          _date = '';
                        });
                        _applyCriteria();
                      }
                    },
                  ),
                  if (_date.isNotEmpty)
                    TextButton.icon(
                      onPressed: _chooseDate,
                      icon: const Icon(Icons.edit_calendar_outlined),
                      label: Text('Date : $_date'),
                    ),
                  const SizedBox(height: MakoloSpacing.md),
                  DropdownButtonFormField<String>(
                    key: const Key('discover-search-price'),
                    initialValue: _price,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Budget',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.payments_outlined),
                    ),
                    items: const [
                      DropdownMenuItem(value: '', child: Text('Tous les prix')),
                      DropdownMenuItem(value: 'free', child: Text('Gratuit')),
                      DropdownMenuItem(value: 'paid', child: Text('Payant')),
                    ],
                    onChanged: (value) {
                      setState(() => _price = value ?? '');
                      _applyCriteria();
                    },
                  ),
                ],
              ),
            ),
          ),
          SizedBox(
            height: 48,
            child: ListView(
              key: const Key('discover-search-categories'),
              scrollDirection: Axis.horizontal,
              children: [
                for (final category in const [
                  ('', 'Tout', Icons.apps_rounded),
                  ('transport', 'Voyager', Icons.directions_bus_outlined),
                  ('event', 'Événements', Icons.event_outlined),
                  ('service', 'Services', Icons.handshake_outlined),
                  ('other', 'Autres', Icons.explore_outlined),
                ]) ...[
                  ChoiceChip(
                    label: Text(category.$2),
                    avatar: Icon(category.$3, size: 18),
                    selected: _vertical == category.$1,
                    showCheckmark: false,
                    onSelected: (_) {
                      setState(() => _vertical = category.$1);
                      _applyCriteria();
                    },
                  ),
                  const SizedBox(width: MakoloSpacing.sm),
                ],
              ],
            ),
          ),
          Expanded(
            child: Builder(
              builder: (context) {
                if (!_query.hasCriteria) {
                  return const Center(
                    child: Text('Saisissez ce que vous recherchez.'),
                  );
                }
                final source = widget.repository.itemsSource(_query);
                return StreamBuilder<StoredProjection?>(
                  stream: widget.repository.watchItems(_query),
                  builder: (context, snapshot) {
                    return StreamBuilder<DiscoverySourceState>(
                      stream: widget.repository.watchSource(source),
                      initialData: DiscoverySourceState.unknown,
                      builder: (context, sourceSnapshot) {
                        final projection = snapshot.data;
                        final sourceState =
                            sourceSnapshot.data ?? DiscoverySourceState.unknown;
                        final freshness = projection == null
                            ? FreshnessState.fresh
                            : DiscoveryRepository.discoveryFreshness.evaluate(
                                projection,
                                now: DateTime.now(),
                                invalidated: sourceState.invalidated,
                              );
                        final selection = _selector.select(
                          projection: projection,
                          hasCriteria: _query.hasCriteria,
                          freshness: freshness,
                          reachability: _reachability(sourceState),
                          failure:
                              sourceState.lastErrorCode != null &&
                                  projection != null
                              ? MakoloFailureCue.recoverable
                              : MakoloFailureCue.none,
                          refreshing: _refreshing,
                          sourceErrorCode: sourceState.lastErrorCode,
                        );
                        return RefreshIndicator(
                          onRefresh: () => _refreshPage(_query),
                          child: DiscoveryExplorationView(
                            selection: selection,
                            onOpen: _open,
                            onSave: (item) => _saveDiscoveryPossibility(
                              widget.repository,
                              item,
                              _query,
                            ),
                            baseUri: widget.repository.api.baseUri,
                            shareApi: widget.repository.api,
                            onPage: _movePage,
                            onRetry: () {
                              if (sourceState.lastErrorCode ==
                                  'continuation_rejected') {
                                final reset = _query.copyWith(page: 1);
                                setState(() => _query = reset);
                                unawaited(_refreshPage(reset));
                              } else {
                                unawaited(_refreshPage(_query));
                              }
                            },
                            onResetCriteria: _resetCriteria,
                          ),
                        );
                      },
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class DiscoveryMapScreen extends StatefulWidget {
  const DiscoveryMapScreen({
    super.key,
    required this.repository,
    required this.mapConfig,
    required this.onOpenOccurrence,
  });

  final DiscoveryRepository repository;
  final MakoloMapsConfig mapConfig;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<DiscoveryMapScreen> createState() => _DiscoveryMapScreenState();
}

class _DiscoveryMapScreenState extends State<DiscoveryMapScreen> {
  static const _selector = DiscoverySelector();
  static const _query = DiscoveryQuery();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readItems(_query);
    if (local == null || local.schemaVersion != 1) {
      await _refresh();
      return;
    }
    try {
      DiscoveryWire.validateData(local.payload);
    } on FormatException {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(_query);
    } on Object {
      // Existing Discovery field remains available.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Carte'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchItems(_query),
        builder: (context, snapshot) {
          final selection = _selector.select(
            projection: snapshot.data,
            hasCriteria: _query.hasCriteria,
            refreshing: _refreshing,
          );
          return DiscoverySpatialView(
            selection: selection,
            mapConfig: widget.mapConfig,
            onSave: (item) =>
                _saveDiscoveryPossibility(widget.repository, item, _query),
            baseUri: widget.repository.api.baseUri,
            shareApi: widget.repository.api,
            onRetry: () => unawaited(_refresh()),
            onOpen: (item) {
              final occurrenceId = item.occurrenceId;
              if (occurrenceId != null) {
                widget.onOpenOccurrence(occurrenceId);
              }
            },
          );
        },
      ),
    );
  }
}

class DiscoveryItemDetailScreen extends StatefulWidget {
  const DiscoveryItemDetailScreen({
    super.key,
    required this.family,
    required this.id,
    required this.repository,
  });

  final String family;
  final String id;
  final DiscoveryRepository repository;

  @override
  State<DiscoveryItemDetailScreen> createState() =>
      _DiscoveryItemDetailScreenState();
}

class _DiscoveryItemDetailScreenState extends State<DiscoveryItemDetailScreen> {
  static const _selector = DiscoverySelector();
  bool _refreshing = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant DiscoveryItemDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.family != widget.family || oldWidget.id != widget.id) {
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() async {
    // Stale-while-revalidate: cached facts can render immediately, but the
    // server must re-evaluate actions and private visibility on N2 entry.
    await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItem(widget.family, widget.id);
    } on Object {
      // Preserve local item if present.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _setSaved(bool saved) async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.setSaved(
        family: widget.family,
        id: widget.id,
        saved: saved,
      );
    } on Object {
      await _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Le changement n’a pas été confirmé. L’état serveur a été relu.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchItem(widget.family, widget.id),
      builder: (context, snapshot) {
        DiscoveryItemPresentation? item;
        var invalidDetail = false;
        try {
          item = _selector.detail(snapshot.data);
        } on FormatException {
          invalidDetail = true;
        }
        return Scaffold(
          appBar: AppBar(
            title: const Text('Possibilité'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: item == null
              ? _refreshing
                    ? const MakoloLoadingState(label: 'Mise à jour…')
                    : MakoloErrorState(
                        message: invalidDetail
                            ? 'La réponse de cette possibilité est incompatible.'
                            : 'Ce contenu n’est pas disponible.',
                        onRetry: _refresh,
                      )
              : ListView(
                  key: const Key('discover-personal-n2'),
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 1040),
                        child: DiscoveryPossibilityUnit(
                          item: item,
                          detailMode: true,
                          onOpen: () {},
                          onOwnerDepth: (path) => context.push(path),
                          onSave:
                              (item.savedState == 'saved'
                                  ? item.canUnsave
                                  : item.canSave)
                              ? () => _setSaved(item!.savedState != 'saved')
                              : null,
                          shareApi: widget.repository.api,
                          shareAuthenticated: true,
                          baseUri: widget.repository.api.baseUri,
                        ),
                      ),
                    ),
                  ],
                ),
        );
      },
    );
  }
}

class ActivityDetailScreen extends StatefulWidget {
  const ActivityDetailScreen({
    super.key,
    required this.activityId,
    required this.repository,
    required this.onOpenOccurrence,
  });

  final String activityId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<ActivityDetailScreen> createState() => _ActivityDetailScreenState();
}

class _ActivityDetailScreenState extends State<ActivityDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant ActivityDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.activityId != widget.activityId) {
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() => _refresh();

  Future<void> _refresh() async {
    if (_refreshing) return;
    final requestedId = widget.activityId;
    setState(() => _refreshing = true);
    try {
      // Always revalidate N3 on entry even when an N1 preview exists.
      await widget.repository.refreshActivity(requestedId);
    } on Object {
      // The owner source records errors and discards revoked keyed details.
    } finally {
      if (mounted) {
        setState(() => _refreshing = false);
        if (widget.activityId != requestedId) unawaited(_refresh());
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchActivityPreview(widget.activityId),
      builder: (context, previewSnapshot) {
        return StreamBuilder<StoredProjection?>(
          stream: widget.repository.watchActivity(widget.activityId),
          builder: (context, snapshot) {
            final activity =
                _selector.activity(snapshot.data) ??
                _selector.activityPreview(previewSnapshot.data);
            return Scaffold(
              appBar: AppBar(
                title: const Text('Activité'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: activity == null
                    ? _refreshing
                          ? const MakoloLoadingState(label: 'Mise à jour…')
                          : MakoloErrorState(
                              message: 'Ce contenu n’est pas disponible.',
                              onRetry: _refresh,
                            )
                    : ListView(
                        padding: const EdgeInsets.only(
                          bottom: MakoloSpacing.xl,
                        ),
                        children: [
                          MakoloDetailHeader(
                            eyebrow: activity.vertical,
                            title: activity.title,
                            subtitle: activity.summary.isEmpty
                                ? null
                                : activity.summary,
                            status: activity.state == null
                                ? null
                                : MakoloStatus(label: activity.state!),
                            metadata: [
                              if (activity.owner != null)
                                MakoloMetadataItem(
                                  activity.owner!,
                                  icon: Icons.business_outlined,
                                ),
                              if (activity.availability != null)
                                MakoloMetadataItem(
                                  activity.availability!,
                                  icon: Icons.event_available_outlined,
                                ),
                            ],
                          ),
                          if (activity.occurrences.isNotEmpty)
                            MakoloSection(
                              title: 'Dates et réalisations',
                              child: Column(
                                children: [
                                  for (
                                    var index = 0;
                                    index < activity.occurrences.length;
                                    index++
                                  ) ...[
                                    MakoloCard(
                                      onTap: () => widget.onOpenOccurrence(
                                        activity.occurrences[index].id,
                                      ),
                                      child: MakoloStatusMetadataAction(
                                        title:
                                            activity.occurrences[index].label,
                                        status:
                                            activity.occurrences[index].state ==
                                                null
                                            ? null
                                            : MakoloStatus(
                                                label: activity
                                                    .occurrences[index]
                                                    .state!,
                                              ),
                                        metadata: [
                                          if (activity
                                                  .occurrences[index]
                                                  .timing !=
                                              null)
                                            MakoloMetadataItem(
                                              activity
                                                  .occurrences[index]
                                                  .timing!,
                                              icon: Icons.schedule_outlined,
                                            ),
                                        ],
                                        action: const Icon(
                                          Icons.chevron_right_rounded,
                                        ),
                                      ),
                                    ),
                                    if (index < activity.occurrences.length - 1)
                                      const SizedBox(height: MakoloSpacing.sm),
                                  ],
                                ],
                              ),
                            ),
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

class OccurrenceDetailScreen extends StatefulWidget {
  const OccurrenceDetailScreen({
    super.key,
    required this.occurrenceId,
    required this.repository,
    required this.onOpenActivity,
    this.onOpenDayOf,
  });

  final String occurrenceId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final VoidCallback? onOpenDayOf;

  @override
  State<OccurrenceDetailScreen> createState() => _OccurrenceDetailScreenState();
}

class _OccurrenceDetailScreenState extends State<OccurrenceDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant OccurrenceDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.occurrenceId != widget.occurrenceId) {
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() => _refresh();

  Future<void> _refresh() async {
    if (_refreshing) return;
    final requestedId = widget.occurrenceId;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshOccurrence(requestedId);
    } on Object {
      // Owner checks access and current state on each N3 entry.
    } finally {
      if (mounted) {
        setState(() => _refreshing = false);
        if (widget.occurrenceId != requestedId) unawaited(_refresh());
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchOccurrencePreview(widget.occurrenceId),
      builder: (context, previewSnapshot) {
        return StreamBuilder<StoredProjection?>(
          stream: widget.repository.watchOccurrence(widget.occurrenceId),
          builder: (context, snapshot) {
            final occurrence =
                _selector.occurrence(snapshot.data) ??
                _selector.occurrencePreview(previewSnapshot.data);
            return Scaffold(
              appBar: AppBar(
                title: const Text('Occurrence'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: occurrence == null
                    ? _refreshing
                          ? const MakoloLoadingState(label: 'Mise à jour…')
                          : MakoloErrorState(
                              message: 'Ce contenu n’est pas disponible.',
                              onRetry: _refresh,
                            )
                    : ListView(
                        padding: const EdgeInsets.only(
                          bottom: MakoloSpacing.xl,
                        ),
                        children: [
                          MakoloDetailHeader(
                            eyebrow: 'Occurrence',
                            title: occurrence.activityTitle,
                            status: occurrence.state == null
                                ? null
                                : MakoloStatus(label: occurrence.state!),
                            metadata: [
                              if (occurrence.timing != null)
                                MakoloMetadataItem(
                                  occurrence.timing!,
                                  icon: Icons.schedule_outlined,
                                ),
                              if (occurrence.place != null)
                                MakoloMetadataItem(
                                  occurrence.place!,
                                  icon: Icons.place_outlined,
                                ),
                              if (occurrence.availability != null)
                                MakoloMetadataItem(
                                  occurrence.availability!,
                                  icon: Icons.event_available_outlined,
                                ),
                            ],
                          ),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: MakoloSpacing.inner,
                            ),
                            child: OutlinedButton.icon(
                              onPressed: () =>
                                  widget.onOpenActivity(occurrence.activityId),
                              icon: const Icon(Icons.arrow_back_rounded),
                              label: const Text('Voir l’activité'),
                            ),
                          ),
                          if (occurrence.canOpenDayOf)
                            Padding(
                              padding: const EdgeInsets.fromLTRB(
                                MakoloSpacing.inner,
                                MakoloSpacing.md,
                                MakoloSpacing.inner,
                                0,
                              ),
                              child: MakoloAttentionBlock(
                                title: 'Jour J disponible',
                                body:
                                    'Les informations utiles pour le moment venu '
                                    'sont disponibles.',
                                icon: Icons.directions_walk_rounded,
                                action: widget.onOpenDayOf == null
                                    ? null
                                    : FilledButton.icon(
                                        onPressed: widget.onOpenDayOf,
                                        icon: const Icon(
                                          Icons.directions_walk_rounded,
                                        ),
                                        label: const Text('Ouvrir le Jour J'),
                                      ),
                              ),
                            ),
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
