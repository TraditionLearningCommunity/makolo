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
import '../../presentation/fields/discovery_filter_fields.dart';
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

/// Device presentation cursor only; the signed server continuation stays
/// opaque. Never synthesize new possibilities or authorization from it.
DiscoveryQuery? retainedDiscoveryPosition(StoredProjection? marker) {
  if (marker?.kind != 'discovery.presentation-position' ||
      marker?.schemaVersion != 1) {
    return null;
  }
  final page = marker!.payload['page'];
  final continuation = marker.payload['continuation'];
  if (page is! int ||
      page < 2 ||
      continuation is! String ||
      continuation.isEmpty) {
    return null;
  }
  return const DiscoveryQuery().copyWith(
    page: page,
    continuation: continuation,
  );
}

/// Restore only presentation hints saved in the current Profile scope.
/// Never convert a screen position into server-owned data.
double? retainedDiscoveryScrollOffset(StoredProjection? marker) {
  if (marker?.kind != 'discovery.presentation-position' ||
      marker?.schemaVersion != 1)
    return null;
  final value = marker!.payload['scroll_offset'];
  if (value is! num || !value.isFinite || value < 0) return null;
  return value.toDouble();
}

String? retainedDiscoveryFocusedCandidate(StoredProjection? marker) {
  if (marker?.kind != 'discovery.presentation-position' ||
      marker?.schemaVersion != 1)
    return null;
  final key = marker!.payload['selected_candidate_key'];
  return key is String && key.isNotEmpty ? key : null;
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
  final Map<String, Future<void>> _pageRequests = {};
  final ScrollController _fieldScroll = ScrollController();
  Timer? _positionDebounce;
  double? _pendingScrollRestore;
  String? _focusedCandidateKey;

  static const _positionProjection = 'discovery.presentation-position';

  @override
  void initState() {
    super.initState();
    _fieldScroll.addListener(() {
      _positionDebounce?.cancel();
      _positionDebounce = Timer(const Duration(milliseconds: 650), () {
        if (mounted) unawaited(_rememberPosition(_query));
      });
    });
    widget.repository.rememberExploration(_query);
    unawaited(_restorePositionThenAcquire());
  }

  @override
  void dispose() {
    _positionDebounce?.cancel();
    unawaited(_rememberPosition(_query));
    _fieldScroll.dispose();
    super.dispose();
  }

  Future<void> _restorePositionThenAcquire() async {
    try {
      final initial = _query;
      final marker = await widget.repository.store.readProjection(
        _positionProjection,
        resourceKey: initial.mapFingerprint,
      );
      _pendingScrollRestore = retainedDiscoveryScrollOffset(marker);
      _focusedCandidateKey = retainedDiscoveryFocusedCandidate(marker);
      final restored = retainedDiscoveryPosition(marker);
      if (restored != null) {
        final known = await widget.repository.readItems(restored);
        final source = await widget.repository.readSource(
          widget.repository.itemsSource(restored),
        );
        if (known != null &&
            !source.ownerUnavailable &&
            source.lastErrorCode != 'continuation_rejected' &&
            mounted &&
            identical(_query, initial)) {
          setState(() => _query = restored);
          widget.repository.rememberExploration(restored);
        }
      }
    } on Object {
      // A missing or outdated cursor never prevents the initial field.
    }
    if (mounted) {
      setState(() {});
      await _acquire();
    }
  }

  Future<void> _rememberPosition(DiscoveryQuery current) async {
    try {
      await widget.repository.store.putProjection(
        kind: _positionProjection,
        resourceKey: const DiscoveryQuery().mapFingerprint,
        schemaVersion: 1,
        payload: {
          'page': current.page,
          'continuation': current.continuation,
          'scroll_offset': _fieldScroll.hasClients
              ? _fieldScroll.offset
              : (_pendingScrollRestore ?? 0.0),
          'selected_candidate_key': _focusedCandidateKey,
        },
      );
    } on Object {
      // The current presentation remains usable without this hint.
    }
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
      } else {
        // A fresh local field also gets an invisible next lot when possible.
        unawaited(_prefetchNext(_query));
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
        await widget.repository.store.deleteProjection(
          _positionProjection,
          resourceKey: const DiscoveryQuery().mapFingerprint,
        );
        if (mounted && identical(current, _query)) {
          setState(() => _query = const DiscoveryQuery());
          widget.repository.rememberExploration(_query);
        }
      }
      await widget.repository.refreshItems(_query);
      unawaited(_prefetchNext(_query));
    } on Object {
      if (mounted) setState(() => _acquisitionFailed = true);
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  /// Share one in-flight request between invisible prefetch and visible
  /// pagination. No extra ranking, no duplicate owner request.
  Future<void> _acquirePage(DiscoveryQuery query) async {
    if (await widget.repository.readItems(query) != null) return;
    final key = query.fingerprint;
    final running = _pageRequests[key];
    if (running != null) {
      await running;
      return;
    }
    final request = widget.repository.refreshItems(query);
    _pageRequests[key] = request;
    try {
      await request;
    } finally {
      _pageRequests.remove(key);
    }
  }

  /// One invisible server continuation. A failed transport retains all
  /// existing presentation and never fabricates another result.
  Future<void> _prefetchNext(DiscoveryQuery current) async {
    if (!mounted || !identical(current, _query)) return;
    try {
      final currentPage = await widget.repository.readItems(current);
      if (currentPage == null) return;
      final collection = _selector.collection(currentPage);
      final token = collection.continuationToken;
      if (!collection.hasNext || token == null || token.isEmpty) return;
      final next = current.copyWith(
        page: current.page + 1,
        continuation: token,
      );
      await _acquirePage(next);
    } on Object {
      // The existing field remains readable on network failure.
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
      if (projection == null) {
        throw const FormatException('Missing Discovery field');
      }
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
      // An already acquired invisible page is usable without any request.
      // Only missing pages require the server; offline is not a new screen.
      var retained = await widget.repository.readItems(next);
      if (retained == null) {
        await _acquirePage(next);
        final source = await widget.repository.readSource(
          widget.repository.itemsSource(next),
        );
        retained = await widget.repository.readItems(next);
        if (source.lastErrorCode != null || retained == null) {
          throw StateError('Discovery continuation unavailable');
        }
      }
      final received = _selector.collection(retained);
      if (received.page != next.page) {
        throw const FormatException('Incompatible local continuation');
      }
      if (!mounted || !identical(current, _query)) return;
      // Materialize only on actual user advancement, never during invisible
      // prefetch. This trims older seen rows without losing the next cursor.
      await widget.repository.retainPresentedWindow(next);
      if (!mounted || !identical(current, _query)) return;
      setState(() => _query = next);
      widget.repository.rememberExploration(next);
      await _rememberPosition(next);
      unawaited(_prefetchNext(next));
    } on Object {
      if (mounted && identical(current, _query)) {
        setState(() => _loadMoreFailed = true);
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _open(DiscoveryItemPresentation item) {
    unawaited(_rememberPosition(_query));
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
            if (_pendingScrollRestore != null && projection != null) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (!mounted ||
                    !_fieldScroll.hasClients ||
                    _pendingScrollRestore == null)
                  return;
                final restored = _pendingScrollRestore!;
                _pendingScrollRestore = null;
                _fieldScroll.jumpTo(
                  restored.clamp(0.0, _fieldScroll.position.maxScrollExtent),
                );
              });
            }
            return RefreshIndicator(
              onRefresh: _refreshItems,
              child: DiscoveryExplorationView(
                selection: selection,
                onOpen: _open,
                onSave: (item) =>
                    _saveDiscoveryPossibility(widget.repository, item, _query),
                baseUri: widget.repository.api.baseUri,
                shareApi: widget.repository.api,
                fieldKey: _query.mapFingerprint,
                scrollController: _fieldScroll,
                initialFocusedCandidateKey: _focusedCandidateKey,
                onFocusedCandidateChanged: (key) {
                  _focusedCandidateKey = key;
                  unawaited(_rememberPosition(_query));
                },
                onMap: (selected) {
                  unawaited(_rememberPosition(_query));
                  context.push(
                    _query.routeLocation(
                      '/discover/map',
                      selectedCandidateKey: selected,
                    ),
                  );
                },
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
    this.initialQuery = const DiscoveryQuery(),
    this.initialSelectedCandidateKey,
    this.location,
    this.geoSearch,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;
  final LocationCapability? location;
  final GeoSearchGateway? geoSearch;
  final DiscoveryQuery initialQuery;
  final String? initialSelectedCandidateKey;

  @override
  State<DiscoverySearchScreen> createState() => _DiscoverySearchScreenState();
}

class _DiscoverySearchScreenState extends State<DiscoverySearchScreen> {
  static const _selector = DiscoverySelector();
  final _search = TextEditingController();
  final _place = TextEditingController();
  final _filterRevision = ValueNotifier<int>(0);
  GeoSuggestion? _selectedPlace;
  String _when = '';
  String _date = '';
  String _price = '';
  String _vertical = '';
  String? _locationMessage;
  late final ProgressiveSearchCoordinator _searchCoordinator;
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;
  final Map<int, String> _pageTokens = {};
  String? _selectedCandidateKey;

  @override
  void initState() {
    super.initState();
    _query = widget.initialQuery;
    widget.repository.rememberExploration(_query);
    _selectedCandidateKey = widget.initialSelectedCandidateKey;
    if (_query.page > 1 && _query.continuation != null) {
      _pageTokens[_query.page] = _query.continuation!;
    }
    _search.text = _query.text;
    _place.text = _query.place;
    _when = _query.date.isNotEmpty ? 'custom' : _query.when;
    _date = _query.date;
    _price = _query.price;
    _vertical = _query.vertical;
    _searchCoordinator = ProgressiveSearchCoordinator(onSearch: _loadRevision);
    if (_query.hasCriteria) {
      _refreshing = true;
      _searchCoordinator.changed(immediate: true);
    }
  }

  @override
  void dispose() {
    _searchCoordinator.dispose();
    _search.dispose();
    _place.dispose();
    _filterRevision.dispose();
    super.dispose();
  }

  void _applyCriteria({bool immediate = true}) {
    _filterRevision.value++;
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
      _date =
          '${chosen.year.toString().padLeft(4, '0')}-'
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
      setState(
        () => _locationMessage =
            'Position indisponible. La recherche par mots-clés reste possible.',
      );
      return;
    }
    final result = await location.current();
    if (!mounted) return;
    if (!result.available || result.fix == null) {
      setState(
        () => _locationMessage =
            'Position indisponible. La recherche par mots-clés reste possible.',
      );
      return;
    }
    _place.clear();
    setState(() {
      // A named place and the device position are alternative spatial frames.
      _selectedPlace = null;
      _query = _query.copyWith(
        place: '',
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
    _pageTokens.clear();
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
    widget.repository.rememberExploration(query);
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
    if (page == 1) {
      token = null;
    } else if (page == current.page + 1) {
      final projection = await widget.repository.readItems(current);
      if (projection == null) return;
      try {
        final collection = _selector.collection(projection);
        if (!collection.hasNext) return;
        token = collection.continuationToken;
      } on FormatException {
        return;
      }
      if (token == null || token.isEmpty) return;
    } else {
      token = _pageTokens[page];
      if (token == null) {
        // A deep-linked older page has no known signed predecessor cursor.
        // Offer the first page with the same criteria instead of guessing.
        unawaited(_navigateToPage(1));
        return;
      }
    }
    if (!mounted || !identical(current, _query)) return;
    if (page > 1 && token != null) _pageTokens[page] = token;
    final query = current.copyWith(
      page: page,
      continuation: token,
      clearContinuation: page == 1,
    );
    setState(() => _query = query);
    widget.repository.rememberExploration(query);
    unawaited(_refreshPage(query));
  }

  Future<void> _refreshPage(DiscoveryQuery query) async {
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // Existing results remain visible.
    } finally {
      if (mounted && identical(query, _query)) {
        setState(() => _refreshing = false);
      }
    }
  }

  void _open(DiscoveryItemPresentation item) {
    // The central owner action may skip N2. Opening the item itself always
    // deepens the same possibility, including Activity-based verticals.
    widget.onOpenItem(item.family, item.id);
  }

  void _clearFilters() {
    _place.clear();
    setState(() {
      _selectedPlace = null;
      _pageTokens.clear();
      _when = '';
      _date = '';
      _price = '';
      _vertical = '';
      _locationMessage = null;
      _query = _query.copyWith(clearLocation: true, clearContinuation: true);
    });
    _applyCriteria();
  }

  void _resetCriteria() {
    _searchCoordinator.invalidate();
    _pageTokens.clear();
    _search.clear();
    _place.clear();
    _selectedPlace = null;
    _when = '';
    _date = '';
    _price = '';
    _vertical = '';
    setState(() {
      _query = const DiscoveryQuery();
      widget.repository.rememberExploration(_query);
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

  Widget _searchControls() => Column(
    mainAxisSize: MainAxisSize.min,
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
          showResultsAction: true,
          onClearFilters: _clearFilters,
          hasActiveFilters:
              _place.text.trim().isNotEmpty ||
              _when.isNotEmpty ||
              _date.isNotEmpty ||
              _price.isNotEmpty ||
              _query.latitude != null,
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
              suffixIcon: _search.text.isEmpty
                  ? null
                  : IconButton(
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
          filters: const SizedBox.shrink(),
          filtersRefresh: _filterRevision,
          filtersBuilder: (_) => DiscoveryFilterFields(
            keyPrefix: 'discover-search',
            placeController: _place,
            geoSearch: widget.geoSearch,
            when: _when,
            date: _date,
            price: _price,
            onPlaceSelected: (place) {
              setState(() {
                _selectedPlace = place;
                _query = _query.copyWith(clearLocation: true);
                _locationMessage = null;
              });
              _applyCriteria();
            },
            onPlaceEdited: () {
              _selectedPlace = null;
              if (_query.latitude != null) {
                setState(() {
                  _query = _query.copyWith(clearLocation: true);
                  _locationMessage = null;
                });
              }
              _applyCriteria(immediate: false);
            },
            onPlaceSubmitted: () => _applyCriteria(),
            onWhenChanged: (value) {
              setState(() {
                _when = value;
                _date = '';
              });
              _applyCriteria();
            },
            onChooseDate: () => unawaited(_chooseDate()),
            onPriceChanged: (value) {
              setState(() => _price = value);
              _applyCriteria();
            },
            extra: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                OutlinedButton.icon(
                  key: const Key('discover-search-nearby'),
                  onPressed: _toggleNearby,
                  icon: Icon(
                    _query.latitude == null
                        ? Icons.near_me_outlined
                        : Icons.location_off_outlined,
                  ),
                  label: Text(
                    _query.latitude == null
                        ? 'Autour de moi · 25 km'
                        : 'Retirer « Autour de moi »',
                  ),
                ),
                if (_locationMessage != null) Text(_locationMessage!),
              ],
            ),
          ),
        ),
      ),
      DiscoveryCategoryChips(
        selected: _vertical,
        listKey: const Key('discover-search-categories'),
        onSelected: (value) {
          setState(() => _vertical = value);
          _applyCriteria();
        },
      ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rechercher'),
        actions: [
          IconButton(
            key: const Key('discover-search-open-map'),
            tooltip: 'Voir ces critères sur la carte',
            onPressed: _query.hasCriteria
                ? () => context.push(_query.routeLocation('/discover/map'))
                : null,
            icon: const Icon(Icons.map_outlined),
          ),
        ],
      ),
      body: Column(
        children: [
          _searchControls(),
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
                            fieldKey: _query.mapFingerprint,
                            initialFocusedCandidateKey: _selectedCandidateKey,
                            onFocusedCandidateChanged: (key) =>
                                _selectedCandidateKey = key,
                            onMap: (selected) => context.push(
                              _query.routeLocation(
                                '/discover/map',
                                selectedCandidateKey: selected,
                              ),
                            ),
                            onPage: _movePage,
                            onRetry: () {
                              if (sourceState.lastErrorCode ==
                                  'continuation_rejected') {
                                final reset = _query.copyWith(page: 1);
                                setState(() => _query = reset);
                                widget.repository.rememberExploration(reset);
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
    this.onOpenItem,
    this.query = const DiscoveryQuery(),
    this.initialSelectedCandidateKey,
  });

  final DiscoveryRepository repository;
  final MakoloMapsConfig mapConfig;
  final ValueChanged<String> onOpenOccurrence;
  final void Function(String family, String id)? onOpenItem;
  final DiscoveryQuery query;
  final String? initialSelectedCandidateKey;

  @override
  State<DiscoveryMapScreen> createState() => _DiscoveryMapScreenState();
}

class _DiscoveryMapScreenState extends State<DiscoveryMapScreen> {
  static const _selector = DiscoverySelector();
  late DiscoveryQuery _query;
  bool _refreshing = false;
  bool _loadMoreFailed = false;
  String? _selectedCandidateKey;
  final Map<int, String> _pageTokens = {};

  @override
  void initState() {
    super.initState();
    _query = widget.query;
    widget.repository.rememberExploration(_query);
    _selectedCandidateKey = widget.initialSelectedCandidateKey;
    if (_query.page > 1 && _query.continuation != null) {
      _pageTokens[_query.page] = _query.continuation!;
    }
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant DiscoveryMapScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.query.fingerprint != widget.query.fingerprint) {
      _query = widget.query;
      widget.repository.rememberExploration(_query);
      _selectedCandidateKey = widget.initialSelectedCandidateKey;
      _pageTokens.clear();
      if (_query.page > 1 && _query.continuation != null) {
        _pageTokens[_query.page] = _query.continuation!;
      }
      _loadMoreFailed = false;
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() async {
    final current = _query;
    try {
      final local = await widget.repository.readItems(current);
      if (local == null || local.schemaVersion != 1) {
        await _refresh();
        return;
      }
      try {
        DiscoveryWire.validateData(local.payload);
      } on FormatException {
        await _refresh();
      }
    } on Object {
      // A missing field is a recoverable source failure, not an empty map.
      if (mounted && identical(current, _query)) await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing || !mounted) return;
    final current = _query;
    setState(() => _refreshing = true);
    var rejected = false;
    try {
      await widget.repository.refreshItems(current);
      final source = await widget.repository.readSource(
        widget.repository.itemsSource(current),
      );
      rejected = source.lastErrorCode == 'continuation_rejected';
    } on Object {
      // The same field and any acquired items remain visible on failure.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
    if (rejected && current.page > 1 && mounted && identical(current, _query)) {
      final first = current.copyWith(page: 1, clearContinuation: true);
      setState(() {
        _query = first;
        widget.repository.rememberExploration(first);
        _pageTokens.clear();
        _loadMoreFailed = false;
      });
      await _refresh();
    }
  }

  Future<void> _navigateToPage(int target) async {
    if (_refreshing || !mounted || target < 1) return;
    final current = _query;
    if (target == current.page) return;
    try {
      String? token;
      if (target == 1) {
        token = null;
      } else if (target == current.page + 1) {
        final stored = await widget.repository.readItems(current);
        if (stored == null) return;
        final collection = _selector.collection(stored);
        if (!collection.hasNext) return;
        token = collection.continuationToken;
        if (token == null || token.isEmpty) return;
      } else {
        token = _pageTokens[target];
        if (token == null) {
          // No invented signed token for a page not previously visited.
          await _navigateToPage(1);
          return;
        }
      }
      if (!mounted || !identical(current, _query)) return;
      final next = current.copyWith(
        page: target,
        continuation: token,
        clearContinuation: target == 1,
      );
      if (token != null) _pageTokens[target] = token;
      var acquired = await widget.repository.readItems(next);
      if (acquired == null) {
        await widget.repository.refreshItems(next);
        final source = await widget.repository.readSource(
          widget.repository.itemsSource(next),
        );
        if (source.lastErrorCode != null) {
          if (source.lastErrorCode == 'continuation_rejected') {
            final first = current.copyWith(page: 1, clearContinuation: true);
            if (mounted && identical(current, _query)) {
              setState(() {
                _query = first;
                widget.repository.rememberExploration(first);
                _pageTokens.clear();
              });
              unawaited(_refresh());
            }
            return;
          }
          throw StateError('Continuation de carte indisponible');
        }
        acquired = await widget.repository.readItems(next);
      }
      if (!mounted || !identical(current, _query)) return;
      if (acquired == null ||
          _selector.collection(acquired).page != next.page) {
        throw const FormatException('Page de carte incompatible');
      }
      if (next.page > 1) await widget.repository.retainPresentedWindow(next);
      if (!mounted || !identical(current, _query)) return;
      setState(() {
        _query = next;
        widget.repository.rememberExploration(next);
        _loadMoreFailed = false;
      });
    } on Object {
      if (mounted && identical(current, _query)) {
        setState(() => _loadMoreFailed = true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Carte'),
        actions: [
          IconButton(
            key: const Key('discover-map-open-search'),
            tooltip: 'Rechercher avec les mêmes critères',
            onPressed: () => context.push(
              _query.routeLocation(
                '/discover/search',
                selectedCandidateKey: _selectedCandidateKey,
              ),
            ),
            icon: const Icon(Icons.search_rounded),
          ),
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
          return StreamBuilder<DiscoverySourceState>(
            stream: widget.repository.watchSource(
              widget.repository.itemsSource(_query),
            ),
            initialData: DiscoverySourceState.unknown,
            builder: (context, sourceSnapshot) {
              final source =
                  sourceSnapshot.data ?? DiscoverySourceState.unknown;
              final selection = _selector.select(
                projection: snapshot.data,
                hasCriteria: _query.hasCriteria,
                refreshing: _refreshing,
                reachability:
                    source.reachability == ReachabilityState.unreachable
                    ? MakoloReachabilityCue.temporarilyUnavailable
                    : source.lastSuccessAt != null
                    ? MakoloReachabilityCue.reachable
                    : MakoloReachabilityCue.unknown,
                failure:
                    _loadMoreFailed ||
                        source.lastErrorCode != null ||
                        snapshot.hasError ||
                        sourceSnapshot.hasError
                    ? MakoloFailureCue.recoverable
                    : MakoloFailureCue.none,
                sourceErrorCode: source.lastErrorCode,
              );
              return DiscoverySpatialView(
                key: ValueKey('discover-map-field-${_query.mapFingerprint}'),
                selection: selection,
                mapConfig: widget.mapConfig,
                showMapOnCompact: true,
                fieldKey: _query.mapFingerprint,
                initialSelectedCandidateKey: widget.initialSelectedCandidateKey,
                onSelectionChanged: (key) => _selectedCandidateKey = key,
                onPage: (page) => unawaited(_navigateToPage(page)),
                loadMoreFailed: _loadMoreFailed,
                onSave: (item) =>
                    _saveDiscoveryPossibility(widget.repository, item, _query),
                baseUri: widget.repository.api.baseUri,
                shareApi: widget.repository.api,
                onRetry: () => unawaited(_refresh()),
                onOpen: (item) {
                  if (widget.onOpenItem != null) {
                    widget.onOpenItem!(item.family, item.id);
                  } else if (item.occurrenceId != null) {
                    widget.onOpenOccurrence(item.occurrenceId!);
                  }
                },
              );
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
  String? _knownSavedTitle;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant ActivityDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.activityId != widget.activityId) {
      _knownSavedTitle = null;
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() async {
    // An Activity already saved in Moi has an owner-known title even when
    // its deeper Activity projection has not yet been downloaded.
    unawaited(_readKnownSavedTitle(widget.activityId));
    await _refresh();
  }

  Future<void> _readKnownSavedTitle(String requestedId) async {
    try {
      final root = await widget.repository.store.readProjection('personal.me');
      final actor = root?.payload['actor'];
      if (actor is! Map ||
          actor['type'] != 'profile' ||
          actor['id']?.toString() != widget.repository.store.profileId) {
        return;
      }
      final considerations = root?.payload['considerations'];
      final saved = considerations is Map ? considerations['bookmarks'] : null;
      final items = saved is Map ? saved['items'] : null;
      if (items is! List) return;
      for (final raw in items) {
        if (raw is! Map || raw['activity'] is! Map) continue;
        final activity = raw['activity'] as Map;
        if (activity['id']?.toString() != requestedId) continue;
        final label = activity['title'];
        if (label is String &&
            label.trim().isNotEmpty &&
            mounted &&
            widget.activityId == requestedId) {
          setState(() => _knownSavedTitle = label.trim());
        }
        break;
      }
    } on Object {
      // No known Activity facts; do not invent a detail or infinite spinner.
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final requestedId = widget.activityId;
    setState(() => _refreshing = true);
    try {
      // Always revalidate N3 on entry even when an N1 preview exists.
      await widget.repository.refreshActivity(requestedId);
      final source = await widget.repository.readSource(
        widget.repository.activitySource(requestedId),
      );
      if (source.ownerUnavailable &&
          mounted &&
          widget.activityId == requestedId) {
        setState(() => _knownSavedTitle = null);
      }
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
                    ? _knownSavedTitle == null
                          ? const SizedBox.expand()
                          : ListView(
                              children: [
                                MakoloDetailHeader(title: _knownSavedTitle!),
                              ],
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
