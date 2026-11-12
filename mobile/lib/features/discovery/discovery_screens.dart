import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../platform/sharing/share_gateway.dart';

import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
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
import '../../platform/maps/makolo_map_view.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_status.dart';
import '../continuity/conversation_context_screen.dart';
import '../continuity/conversation_repository.dart';
import 'detail_selector.dart';
import 'discovery_mature_view.dart';
import 'discovery_repository.dart';
import 'discovery_map_visit_state.dart';
import 'discovery_map_place_search.dart';
import 'discovery_directions_sheet.dart';
import 'discovery_selector.dart';
import 'discovery_unseen_reserve.dart';
import 'discovery_wire.dart';
import 'discovery_watch_create.dart';

/// A newly created Watch is opened only after the Discovery owner returns
/// its canonical identity. Cancel and refusal never navigate.
Future<void> _startDiscoveryWatch(
  BuildContext context,
  DiscoveryRepository repository,
  DiscoveryQuery query,
) async {
  final id = await showDiscoveryWatchCreation(
    context,
    repository: repository,
    query: query,
  );
  if (id != null && context.mounted) {
    context.push('/discover/watches/${Uri.encodeComponent(id)}');
  }
}

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
DiscoveryQuery? retainedDiscoveryPosition(
  StoredProjection? marker, {
  DiscoveryQuery initialQuery = const DiscoveryQuery(),
}) {
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
  return initialQuery.copyWith(page: page, continuation: continuation);
}

/// Restore only presentation hints saved in the current Profile scope.
/// Never convert a screen position into server-owned data.
double? retainedDiscoveryScrollOffset(StoredProjection? marker) {
  if (marker?.kind != 'discovery.presentation-position' ||
      marker?.schemaVersion != 1) {
    return null;
  }
  final value = marker!.payload['scroll_offset'];
  if (value is! num || !value.isFinite || value < 0) return null;
  return value.toDouble();
}

String? retainedDiscoveryFocusedCandidate(StoredProjection? marker) {
  if (marker?.kind != 'discovery.presentation-position' ||
      marker?.schemaVersion != 1) {
    return null;
  }
  final key = marker!.payload['selected_candidate_key'];
  return key is String && key.isNotEmpty ? key : null;
}

class DiscoveryScreen extends StatefulWidget {
  const DiscoveryScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
    this.initialQuery = const DiscoveryQuery(),
  });

  final DiscoveryQuery initialQuery;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;

  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

class _DiscoveryScreenState extends State<DiscoveryScreen> {
  static const _selector = DiscoverySelector();
  late DiscoveryQuery _query;
  bool _refreshing = false;
  bool _acquisitionFailed = false;
  String? _verifiedFieldKey;
  String? _boundFieldKey;
  DiscoveryRepository? _boundRepository;
  late Stream<StoredProjection?> _itemsStream;
  late Stream<DiscoverySourceState> _fieldSourceStream;

  void _bindFieldStreamsIfNeeded() {
    if (_boundFieldKey == _query.fingerprint &&
        identical(_boundRepository, widget.repository)) {
      return;
    }
    _boundFieldKey = _query.fingerprint;
    _boundRepository = widget.repository;
    _itemsStream = widget.repository.watchItems(_query);
    _fieldSourceStream = widget.repository.watchSource(
      widget.repository.itemsSource(_query),
    );
  }

  bool _loadingMore = false;
  bool _loadMoreFailed = false;
  final Map<String, Future<void>> _pageRequests = {};
  DiscoveryUnseenReserve? _unseenReserve;
  String? _unseenField;
  Future<void>? _unseenLoad;

  final ScrollController _fieldScroll = ScrollController();
  Set<String>? _knownCandidateKeys;
  String? _knownCandidateField;
  bool _newPossibilitiesAvailable = false;
  Timer? _positionDebounce;
  double? _pendingScrollRestore;
  String? _focusedCandidateKey;
  int _restoreGeneration = 0;
  int _ownerGeneration = 0;

  static const _positionProjection = 'discovery.presentation-position';

  @override
  void initState() {
    super.initState();
    _query = widget.initialQuery;
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
  void didUpdateWidget(covariant DiscoveryScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.repository, widget.repository) ||
        oldWidget.initialQuery.mapFingerprint !=
            widget.initialQuery.mapFingerprint) {
      // Another viewer or actor cannot inherit a field, position or cursor.
      _query = widget.initialQuery;
      _verifiedFieldKey = null;
      _boundFieldKey = null;
      _boundRepository = null;
      _unseenReserve = null;
      _unseenField = null;
      _knownCandidateKeys = null;
      _knownCandidateField = null;
      _newPossibilitiesAvailable = false;
      _pendingScrollRestore = null;
      _focusedCandidateKey = null;
      _pageRequests.clear();
      _unseenLoad = null;
      ++_restoreGeneration;
      ++_ownerGeneration;
      _refreshing = false;
      _loadingMore = false;
      _positionDebounce?.cancel();
      unawaited(_restorePositionThenAcquire());
    }
  }

  @override
  void dispose() {
    _positionDebounce?.cancel();
    unawaited(_rememberPosition(_query));
    _fieldScroll.dispose();
    super.dispose();
  }

  void _showNewPossibilities() {
    if (_fieldScroll.hasClients) {
      _fieldScroll.animateTo(
        0,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
    }
    setState(() => _newPossibilitiesAvailable = false);
  }

  static int _initialReveal(int count) =>
      count <= 1 ? count : ((count * 2) ~/ 3).clamp(1, count).toInt();

  Future<void> _ensureUnseenReserve(DiscoveryQuery query) async {
    if (_unseenReserve != null && _unseenField == query.mapFingerprint) {
      final root = await widget.repository.readItems(
        query.copyWith(page: 1, clearContinuation: true),
      );
      if (root != null && root.receivedAt == _unseenReserve!.rootReceivedAt) {
        return;
      }
      _unseenReserve = null;
      _unseenField = null;
    }
    final running = _unseenLoad;
    if (running != null) {
      try {
        await running;
      } on Object {
        // Recoverable local corruption must not suppress Discovery.
      }
      if (_unseenReserve != null && _unseenField == query.mapFingerprint) {
        return;
      }
    }
    final request = _loadUnseenReserve(query);
    _unseenLoad = request;
    try {
      await request;
    } on Object {
      // A damaged or unavailable local ledger must not block the owner
      // field. It will be reconstructed from received server items.
    } finally {
      if (identical(_unseenLoad, request)) _unseenLoad = null;
    }
  }

  Future<void> _loadUnseenReserve(DiscoveryQuery query) async {
    final repository = widget.repository;
    final projection = await repository.readItems(query);
    if (projection == null) return;
    final collection = _selector.collection(projection);
    final root = await repository.readItems(
      query.copyWith(page: 1, clearContinuation: true),
    );
    if (root == null) return;
    final saved = await repository.readUnseenReserve(query);
    final reserve =
        saved ?? DiscoveryUnseenReserve(rootReceivedAt: root.receivedAt);
    reserve.observe(collection.items.map((item) => item.wire));
    if (saved == null && reserve.shownKeys.isEmpty) {
      reserve.reveal(
        collection.items.map((item) => item.candidateKey),
        count: _initialReveal(collection.items.length),
      );
    }
    if (!mounted ||
        !identical(widget.repository, repository) ||
        query.mapFingerprint != _query.mapFingerprint) {
      return;
    }
    setState(() {
      _unseenReserve = reserve;
      _unseenField = query.mapFingerprint;
    });
    await repository.saveUnseenReserve(query, reserve);
  }

  Future<void> _restorePositionThenAcquire() async {
    final generation = ++_restoreGeneration;
    final repository = widget.repository;
    final initial = _query;
    bool current() =>
        mounted &&
        generation == _restoreGeneration &&
        identical(widget.repository, repository) &&
        identical(_query, initial);
    try {
      final marker = await repository.store.readProjection(
        _positionProjection,
        resourceKey: initial.mapFingerprint,
      );
      if (!current()) return;
      _pendingScrollRestore = retainedDiscoveryScrollOffset(marker);
      _focusedCandidateKey = retainedDiscoveryFocusedCandidate(marker);
      final restored = retainedDiscoveryPosition(marker, initialQuery: initial);
      if (restored != null) {
        final known = await repository.readItems(restored);
        final source = await repository.readSource(
          repository.itemsSource(restored),
        );
        if (!current()) return;
        if (known != null &&
            !source.ownerUnavailable &&
            source.lastErrorCode != 'continuation_rejected') {
          setState(() => _query = restored);
          repository.rememberExploration(restored);
        }
      }
    } on Object {
      // A missing or outdated cursor never prevents the initial field.
    }
    if (mounted &&
        generation == _restoreGeneration &&
        identical(widget.repository, repository)) {
      setState(() {});
      await _ensureUnseenReserve(_query);
      if (mounted &&
          generation == _restoreGeneration &&
          identical(widget.repository, repository)) {
        await _acquire();
      }
    }
  }

  Future<void> _rememberPosition(DiscoveryQuery current) async {
    try {
      await widget.repository.store.putProjection(
        kind: _positionProjection,
        resourceKey: current.mapFingerprint,
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
    final current = _query;
    final repository = widget.repository;
    bool active() =>
        mounted &&
        identical(repository, widget.repository) &&
        identical(current, _query);
    try {
      final local = await repository.readItems(current);
      if (!active()) return;
      if (local != null) {
        await _ensureUnseenReserve(current);
        if (!active()) return;
        try {
          DiscoveryWire.validateData(local.payload);
          await repository.indexItemPreviews(current);
        } on FormatException {
          // Malformed historical rows cannot become owner-verified previews.
        }
      }
      if (!active()) return;
      if (await repository.hasReusableItems(current)) {
        if (active()) {
          setState(() => _verifiedFieldKey = current.mapFingerprint);
        }
        return;
      }
      if (active()) await _refreshItems();
    } on Object {
      if (active()) setState(() => _acquisitionFailed = true);
    }
  }

  Future<void> _refreshItems() async {
    if (_refreshing || !mounted) return;
    final repository = widget.repository;
    final generation = ++_ownerGeneration;
    final current = _query;
    bool active() =>
        mounted &&
        generation == _ownerGeneration &&
        identical(widget.repository, repository);
    setState(() {
      _refreshing = true;
      _acquisitionFailed = false;
    });
    try {
      final source = await repository.readSource(
        repository.itemsSource(current),
      );
      if (!active() || !identical(current, _query)) return;
      if (source.lastErrorCode == 'continuation_rejected') {
        await repository.store.deleteProjection(
          _positionProjection,
          resourceKey: current.mapFingerprint,
        );
        if (!active() || !identical(current, _query)) return;
        setState(() => _query = widget.initialQuery);
        repository.rememberExploration(_query);
      }
      final refreshed = _query;
      await repository.refreshItems(refreshed);
      final status = await repository.readSource(
        repository.itemsSource(refreshed),
      );
      if (active() &&
          identical(refreshed, _query) &&
          status.lastErrorCode == null &&
          status.lastSuccessAt != null &&
          !status.invalidated) {
        setState(() {
          _verifiedFieldKey = refreshed.mapFingerprint;
          if (refreshed.page == 1) {
            _unseenReserve = null;
            _unseenField = null;
          }
        });
        await _ensureUnseenReserve(refreshed);
      }
    } on Object {
      if (active()) setState(() => _acquisitionFailed = true);
    } finally {
      if (active()) setState(() => _refreshing = false);
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

  /// Append the server's next lot without navigating away or resetting scroll.
  /// The repository composes the locally stored pages by candidate identity.
  Future<void> _loadNextPage() async {
    if (_loadingMore || _refreshing || !mounted) return;
    final current = _query;
    final repository = widget.repository;
    final generation = _ownerGeneration;
    bool active() =>
        mounted &&
        generation == _ownerGeneration &&
        identical(repository, widget.repository) &&
        identical(current, _query);
    setState(() => _loadMoreFailed = false);
    try {
      final projection = await repository.readItems(current);
      if (projection == null) {
        throw const FormatException('Missing Discovery field');
      }
      if (!active()) return;
      final collection = _selector.collection(projection);
      await _ensureUnseenReserve(current);
      if (!active()) return;
      final reserve = _unseenReserve;
      if (reserve != null && _unseenField == current.mapFingerprint) {
        final eligible = collection.items.map((item) => item.candidateKey);
        final pending = reserve.pendingFrom(eligible);
        if (pending.isNotEmpty) {
          reserve.reveal(eligible, count: pending.length);
          await repository.saveUnseenReserve(current, reserve);
          if (active()) setState(() {});
          return;
        }
      }
      if (!collection.hasNext) return;
      final token = collection.continuationToken;
      if (token == null || token.isEmpty) {
        throw const FormatException('Missing Discovery continuation');
      }
      if (!active()) return;
      setState(() => _loadingMore = true);
      final next = current.copyWith(
        page: current.page + 1,
        continuation: token,
      );
      // An already acquired invisible page is usable without any request.
      // Only missing pages require the server; offline is not a new screen.
      var retained = await repository.readItems(next);
      if (retained == null) {
        if (!active()) return;
        await _acquirePage(next);
        if (!active()) return;
        final source = await repository.readSource(
          repository.itemsSource(next),
        );
        retained = await repository.readItems(next);
        if (source.lastErrorCode != null || retained == null) {
          throw StateError('Discovery continuation unavailable');
        }
      }
      if (!active()) return;
      final received = _selector.collection(retained);
      if (received.page != next.page) {
        throw const FormatException('Incompatible local continuation');
      }
      if (!active()) return;
      if (reserve != null && _unseenField == current.mapFingerprint) {
        reserve.observe(received.items.map((item) => item.wire));
        final incomingKeys = received.items.map((item) => item.candidateKey);
        final pending = reserve.pendingFrom(incomingKeys);
        reserve.reveal(incomingKeys, count: _initialReveal(pending.length));
        await repository.saveUnseenReserve(next, reserve);
      }
      if (!active()) return;
      // Materialize only on actual user advancement, never during invisible
      // prefetch. This trims older seen rows without losing the next cursor.
      await repository.retainPresentedWindow(next);
      if (!active()) return;
      setState(() => _query = next);
      repository.rememberExploration(next);
      await _rememberPosition(next);
    } on Object {
      if (active()) {
        setState(() => _loadMoreFailed = true);
      }
    } finally {
      if (mounted &&
          generation == _ownerGeneration &&
          identical(widget.repository, repository)) {
        setState(() => _loadingMore = false);
      }
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
    _bindFieldStreamsIfNeeded();
    return StreamBuilder<StoredProjection?>(
      stream: _itemsStream,
      builder: (context, snapshot) {
        return StreamBuilder<DiscoverySourceState>(
          stream: _fieldSourceStream,
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
            final full = selection.collection;
            final candidateField = _query.mapFingerprint;
            if (_knownCandidateField != candidateField) {
              _knownCandidateField = candidateField;
              _knownCandidateKeys = null;
              _newPossibilitiesAvailable = false;
            }
            if (projection != null && _query.page == 1) {
              final currentKeys = full.items
                  .map((item) => item.candidateKey)
                  .toSet();
              final previous = _knownCandidateKeys;
              if (previous != null &&
                  previous.isNotEmpty &&
                  currentKeys.any((key) => !previous.contains(key)) &&
                  _fieldScroll.hasClients &&
                  _fieldScroll.offset >= 120 &&
                  !_newPossibilitiesAvailable) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted &&
                      _query.mapFingerprint == candidateField &&
                      !_newPossibilitiesAvailable) {
                    setState(() => _newPossibilitiesAvailable = true);
                  }
                });
              }
              _knownCandidateKeys = currentKeys;
            }
            final currentReserve = _unseenField == _query.mapFingerprint
                ? _unseenReserve
                : null;
            final rootChanged =
                currentReserve != null &&
                _query.page == 1 &&
                projection != null &&
                currentReserve.rootReceivedAt != projection.receivedAt;
            final reserve = rootChanged ? null : currentReserve;
            if (rootChanged) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) unawaited(_ensureUnseenReserve(_query));
              });
            }
            final visible = reserve == null
                ? full.items.take(_initialReveal(full.items.length)).toList()
                : full.items
                      .where((item) => reserve.isShown(item.candidateKey))
                      .toList();
            final hiddenOnCurrent = reserve == null
                ? visible.length < full.items.length
                : reserve
                      .pendingFrom(full.items.map((item) => item.candidateKey))
                      .isNotEmpty;
            final visibleWire = visible.map((item) => item.wire).toList();
            final displaySelection = DiscoveryFieldSelection(
              collection: DiscoveryCollectionPresentation(
                items: List.unmodifiable(visible),
                count: full.count,
                page: full.page,
                pageSize: full.pageSize,
                hasNext: full.hasNext || hiddenOnCurrent,
                wire: Map.unmodifiable({
                  ...full.wire,
                  'results': visibleWire,
                  'items': visibleWire,
                }),
              ),
              surface: selection.surface,
              states: hiddenOnCurrent
                  ? Set.unmodifiable(
                      selection.states
                          .where(
                            (state) => state != DiscoveryFieldState.endOfField,
                          )
                          .toSet(),
                    )
                  : selection.states,
            );
            if (_pendingScrollRestore != null && projection != null) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (!mounted ||
                    !_fieldScroll.hasClients ||
                    _pendingScrollRestore == null) {
                  return;
                }
                final restored = _pendingScrollRestore!;
                _pendingScrollRestore = null;
                _fieldScroll.jumpTo(
                  restored.clamp(0.0, _fieldScroll.position.maxScrollExtent),
                );
              });
            }
            return Stack(
              children: [
                RefreshIndicator(
                  onRefresh: _refreshItems,
                  child: DiscoveryExplorationView(
                    selection: displaySelection,
                    onOpen: _open,
                    onSave: _query.isSpace
                        ? null
                        : (item) => _saveDiscoveryPossibility(
                            widget.repository,
                            item,
                            _query,
                          ),
                    baseUri: widget.repository.api.baseUri,
                    shareApi: _query.isSpace ? null : widget.repository.api,
                    profileId: widget.repository.profileId,
                    allowOwnerActions:
                        !_query.isSpace &&
                        !_refreshing &&
                        _verifiedFieldKey == _query.mapFingerprint &&
                        sourceState.lastErrorCode == null &&
                        !sourceState.invalidated,
                    onWatch: _query.isSpace || _query.watchCriteria.isEmpty
                        ? null
                        : () => unawaited(
                            _startDiscoveryWatch(
                              context,
                              widget.repository,
                              _query,
                            ),
                          ),
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
                ),
                if (_newPossibilitiesAvailable)
                  Align(
                    alignment: Alignment.topCenter,
                    child: TextButton.icon(
                      key: const Key('discovery-new-possibilities'),
                      onPressed: _showNewPossibilities,
                      icon: const Icon(Icons.arrow_upward_rounded),
                      label: const Text('De nouvelles possibilités'),
                    ),
                  ),
              ],
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

String _providerFailureMessage(String reason) => switch (reason) {
  'connection_unavailable' => 'Recherche de sources indisponible.',
  'invalid_credentials' => 'Connexion à vérifier pour rechercher des sources.',
  'rate_limited' => 'Limite de recherche atteinte. Réessayez plus tard.',
  'network_unavailable' =>
    'Impossible de rechercher des sources pour le moment.',
  _ => 'Recherche de sources indisponible.',
};

bool _canRepairDiscoveryConnection(String reason) =>
    reason == 'connection_unavailable' || reason == 'invalid_credentials';

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
  String? _selectedWatchId;
  String? _locationMessage;
  late final ProgressiveSearchCoordinator _searchCoordinator;
  DiscoveryQuery _query = const DiscoveryQuery();
  String? _boundResultsKey;
  DiscoveryRepository? _boundResultsRepository;
  late Stream<StoredProjection?> _resultsStream;
  late Stream<DiscoverySourceState> _resultsSourceStream;
  late Stream<StoredProjection?> _watchesStream;

  void _bindResultStreams() {
    if (_boundResultsKey == _query.fingerprint &&
        identical(_boundResultsRepository, widget.repository)) {
      return;
    }
    _boundResultsKey = _query.fingerprint;
    _boundResultsRepository = widget.repository;
    _resultsStream = widget.repository.watchItems(_query);
    _resultsSourceStream = widget.repository.watchSource(
      widget.repository.itemsSource(_query),
    );
  }

  bool _refreshing = false;
  String? _verifiedFieldKey;
  bool _clarifying = false;
  bool _researching = false;
  final Map<int, String> _pageTokens = {};
  String? _selectedCandidateKey;

  @override
  void initState() {
    super.initState();
    _query = widget.initialQuery;
    _watchesStream = widget.repository.watchWatches();
    if (!_query.isSpace) unawaited(_refreshSavedWatches());
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
  void didUpdateWidget(covariant DiscoverySearchScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.repository, widget.repository)) {
      // A new viewer cannot inherit another viewer's filters or watches.
      _searchCoordinator.invalidate();
      _watchesStream = widget.repository.watchWatches();
      _boundResultsKey = null;
      _boundResultsRepository = null;
      _query = widget.initialQuery;
      _selectedCandidateKey = widget.initialSelectedCandidateKey;
      _pageTokens.clear();
      _selectedWatchId = null;
      _verifiedFieldKey = null;
      _search.text = _query.text;
      _place.text = _query.place;
      _when = _query.date.isNotEmpty ? 'custom' : _query.when;
      _date = _query.date;
      _price = _query.price;
      _vertical = _query.vertical;
      if (!_query.isSpace) unawaited(_refreshSavedWatches());
      if (_query.hasCriteria) {
        _refreshing = true;
        _searchCoordinator.changed(immediate: true);
      } else {
        _refreshing = false;
      }
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

  Future<void> _refreshSavedWatches() async {
    try {
      final source = widget.repository.watchesSource();
      final previous = await widget.repository.readSource(source);
      final stored = await widget.repository.store.readProjection(
        DiscoveryRepository.watchesProjectionKind,
      );
      final recentlyConfirmed =
          previous.lastSuccessAt != null &&
          !previous.invalidated &&
          previous.lastErrorCode == null &&
          DateTime.now().toUtc().difference(previous.lastSuccessAt!.toUtc()) <
              const Duration(minutes: 15);
      if (recentlyConfirmed && stored != null) return;
      await widget.repository.refreshWatches();
    } on Object {
      // Visitors have no private watches; keep public search available.
    }
  }

  void _selectSavedWatch(String? id, List<dynamic> rows) {
    if (id == null || id.isEmpty) {
      _resetCriteria();
      return;
    }
    Map? found;
    for (final row in rows) {
      if (row is Map && row['id'] == id) {
        found = row;
        break;
      }
    }
    final criteria = found?['criteria'];
    if (criteria is! Map) return;
    const keys = {
      'q',
      'place',
      'when',
      'period',
      'vertical',
      'price',
      'date',
      'date_from',
      'date_to',
      'lat',
      'lon',
      'radius_km',
    };
    final params = <String, String>{};
    for (final key in keys) {
      final value = criteria[key];
      if (value is String && value.trim().isNotEmpty) {
        params[key] = value.trim();
      }
    }
    DiscoveryQuery query;
    try {
      query = DiscoveryQuery.fromRouteParameters(params);
    } on FormatException {
      return;
    }
    _searchCoordinator.invalidate();
    _pageTokens.clear();
    _search.text = query.text;
    _place.text = query.place;
    _selectedPlace = null;
    _when = query.date.isNotEmpty ? 'custom' : query.when;
    _date = query.date;
    _price = query.price;
    _vertical = query.vertical;
    _filterRevision.value++;
    setState(() {
      _selectedWatchId = id;
      _query = query;
      _refreshing = query.hasCriteria;
    });
    widget.repository.rememberExploration(query);
    if (query.hasCriteria) _searchCoordinator.changed(immediate: true);
  }

  Widget _watchFilter() => _query.isSpace
      ? const SizedBox.shrink()
      : StreamBuilder<StoredProjection?>(
          stream: _watchesStream,
          builder: (context, snapshot) {
            final results = snapshot.data?.payload['results'];
            if (results is! List) return const SizedBox.shrink();
            final watches = results
                .whereType<Map>()
                .where(
                  (row) =>
                      row['id'] is String &&
                      row['name'] is String &&
                      row['criteria'] is Map,
                )
                .toList();
            if (watches.isEmpty) return const SizedBox.shrink();
            final selected = watches.any((row) => row['id'] == _selectedWatchId)
                ? _selectedWatchId
                : null;
            return KeyedSubtree(
              key: ValueKey('discover-watch-choice-$selected'),
              child: DropdownButtonFormField<String>(
                key: const Key('discover-search-watch-filter'),
                initialValue: selected,
                decoration: const InputDecoration(
                  labelText: 'Veilles',
                  prefixIcon: Icon(Icons.radar_outlined),
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem<String>(
                    value: '',
                    child: Text('Toutes les possibilités'),
                  ),
                  for (final watch in watches)
                    DropdownMenuItem<String>(
                      value: watch['id'] as String,
                      child: Text(watch['name'] as String),
                    ),
                ],
                onChanged: (id) => _selectSavedWatch(id, watches),
              ),
            );
          },
        );

  void _applyCriteria({bool immediate = true}) {
    _selectedWatchId = null;
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
      setState(() => _locationMessage = 'Impossible d’obtenir votre position.');
      return;
    }
    final result = await location.current();
    if (!mounted) return;
    if (!result.available || result.fix == null) {
      setState(() => _locationMessage = 'Impossible d’obtenir votre position.');
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

  Future<void> _researchSources() async {
    if (_researching || _search.text.trim().isEmpty) return;
    final requestedText = _search.text.trim();
    setState(() => _researching = true);
    try {
      final result = await widget.repository.researchSources(requestedText);
      if (!mounted || _search.text.trim() != requestedText) return;
      if (result.status == 'unavailable') {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(_providerFailureMessage(result.reason)),
            action: _canRepairDiscoveryConnection(result.reason)
                ? SnackBarAction(
                    label: 'Connexions',
                    onPressed: () => context.push('/connections'),
                  )
                : null,
          ),
        );
        return;
      }
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheetContext) => SafeArea(
          child: FractionallySizedBox(
            heightFactor: 0.75,
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  'Sources pour « $requestedText »',
                  style: Theme.of(sheetContext).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Ces sources ne sont pas confirmées par Makolo.',
                ),
                if (result.leads.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 20),
                    child: Text('Aucune source à afficher.'),
                  ),
                for (final lead in result.leads)
                  Card(
                    child: ListTile(
                      title: Text(lead.label),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (lead.summary.isNotEmpty) Text(lead.summary),
                          const SizedBox(height: 4),
                          Text('${lead.title} · ${lead.url.host}'),
                        ],
                      ),
                      trailing: const Icon(Icons.open_in_new),
                      onTap: () => unawaited(
                        const SystemShareGateway().openExternal(lead.url),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      );
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Impossible de rechercher des sources.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _researching = false);
    }
  }

  Future<void> _clarifySearch() async {
    if (_clarifying || _search.text.trim().isEmpty) return;
    final requestQuery = _query;
    setState(() => _clarifying = true);
    try {
      final result = await widget.repository.clarifySearch(requestQuery);
      if (!mounted || !identical(requestQuery, _query)) return;
      if (result.status == 'applied') {
        final params = result.criteria;
        _searchCoordinator.invalidate();
        _pageTokens.clear();
        _search.text = params['q'] ?? '';
        _place.text = params['place'] ?? '';
        _selectedPlace = null;
        _filterRevision.value++;
        _when = params['when'] ?? '';
        _price = params['price'] ?? '';
        _vertical = params['vertical'] ?? '';
        _date = params['date'] ?? '';
        _searchChanged(_search.text, immediate: true);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Recherche affinée.'),
          ),
        );
      } else {
        final message = result.status == 'unavailable'
            ? _providerFailureMessage(result.reason)
            : 'Aucun nouveau critère trouvé.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(message),
            action:
                result.status == 'unavailable' &&
                    _canRepairDiscoveryConnection(result.reason)
                ? SnackBarAction(
                    label: 'Connexions',
                    onPressed: () => context.push('/connections'),
                  )
                : null,
          ),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible d’affiner la recherche.')),
        );
      }
    } finally {
      if (mounted) setState(() => _clarifying = false);
    }
  }

  Future<void> _loadRevision(int revision) async {
    final query = _query;
    if (!query.hasCriteria) return;
    try {
      await widget.repository.ensureItems(query);
      final status = await widget.repository.readSource(
        widget.repository.itemsSource(query),
      );
      if (mounted &&
          _searchCoordinator.isCurrent(revision) &&
          status.lastErrorCode == null &&
          !status.invalidated &&
          status.lastSuccessAt != null) {
        setState(() => _verifiedFieldKey = query.mapFingerprint);
      }
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

  Future<void> _refreshPage(DiscoveryQuery query, {bool force = false}) async {
    setState(() => _refreshing = true);
    try {
      if (force) {
        await widget.repository.refreshItems(query);
      } else {
        await widget.repository.ensureItems(query);
      }
      final status = await widget.repository.readSource(
        widget.repository.itemsSource(query),
      );
      if (mounted &&
          identical(query, _query) &&
          status.lastErrorCode == null &&
          !status.invalidated &&
          status.lastSuccessAt != null) {
        setState(() => _verifiedFieldKey = query.mapFingerprint);
      }
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
    _selectedWatchId = null;
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
    _selectedWatchId = null;
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
      _query = DiscoveryQuery(
        spaceSlug: widget.initialQuery.spaceSlug,
        spaceId: widget.initialQuery.spaceId,
      );
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
            onChanged: (value) {
              _selectedWatchId = null;
              _searchChanged(value);
            },
            onSubmitted: (value) {
              _selectedWatchId = null;
              _submit(value);
            },
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
                _watchFilter(),
                const SizedBox(height: MakoloSpacing.sm),
                MakoloActionButton(
                  key: const Key('discover-search-nearby'),
                  onPressed: _toggleNearby,
                  appearance: MakoloActionAppearance.secondary,
                  icon: _query.latitude == null
                      ? Icons.near_me_outlined
                      : Icons.location_off_outlined,
                  label: _query.latitude == null
                      ? 'Autour de moi · 25 km'
                      : 'Retirer « Autour de moi »',
                ),
                if (_locationMessage != null) Text(_locationMessage!),
              ],
            ),
          ),
        ),
      ),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: MakoloSpacing.inner),
        child: Row(
          children: [
            OutlinedButton.icon(
              key: const Key('discover-search-clarify'),
              onPressed:
                  _query.isSpace || _clarifying || _search.text.trim().isEmpty
                  ? null
                  : () => unawaited(_clarifySearch()),
              icon: _clarifying
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.tune_rounded),
              label: const Text('Affiner la recherche'),
            ),
            const SizedBox(width: 8),
            const Expanded(
              child: Text(
                'Frais possibles selon le service connecté.',
                style: TextStyle(fontSize: 11),
              ),
            ),
          ],
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(
          MakoloSpacing.inner,
          4,
          MakoloSpacing.inner,
          8,
        ),
        child: Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            key: const Key('discover-search-sources'),
            onPressed:
                _query.isSpace || _researching || _search.text.trim().isEmpty
                ? null
                : () => unawaited(_researchSources()),
            icon: _researching
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.menu_book_outlined),
            label: const Text('Explorer d’autres sources'),
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
                _bindResultStreams();
                return StreamBuilder<StoredProjection?>(
                  stream: _resultsStream,
                  builder: (context, snapshot) {
                    return StreamBuilder<DiscoverySourceState>(
                      stream: _resultsSourceStream,
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
                          onRefresh: () => _refreshPage(_query, force: true),
                          child: DiscoveryExplorationView(
                            selection: selection,
                            onOpen: _open,
                            onSave: _query.isSpace
                                ? null
                                : (item) => _saveDiscoveryPossibility(
                                    widget.repository,
                                    item,
                                    _query,
                                  ),
                            baseUri: widget.repository.api.baseUri,
                            shareApi: _query.isSpace
                                ? null
                                : widget.repository.api,
                            profileId: widget.repository.profileId,
                            allowOwnerActions:
                                !_query.isSpace &&
                                !_refreshing &&
                                _verifiedFieldKey == _query.mapFingerprint &&
                                sourceState.lastErrorCode == null &&
                                !sourceState.invalidated,
                            onWatch:
                                _query.isSpace || _query.watchCriteria.isEmpty
                                ? null
                                : () => unawaited(
                                    _startDiscoveryWatch(
                                      context,
                                      widget.repository,
                                      _query,
                                    ),
                                  ),
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
    this.location,
    this.geoSearch,
    required this.onOpenOccurrence,
    this.onOpenItem,
    this.query = const DiscoveryQuery(),
    this.initialSelectedCandidateKey,
    this.authenticated = false,
  });

  final DiscoveryRepository repository;
  final MakoloMapsConfig mapConfig;
  final LocationCapability? location;
  final GeoSearchGateway? geoSearch;
  final ValueChanged<String> onOpenOccurrence;
  final Future<void> Function(String family, String id)? onOpenItem;
  final bool authenticated;
  final DiscoveryQuery query;
  final String? initialSelectedCandidateKey;

  @override
  State<DiscoveryMapScreen> createState() => _DiscoveryMapScreenState();
}

class _DiscoveryMapScreenState extends State<DiscoveryMapScreen> {
  static const _selector = DiscoverySelector();
  late DiscoveryQuery _query;
  late DiscoveryMapVisitState _visit;
  bool _refreshing = false;
  DiscoveryQuery? _refreshingQuery;
  int _spatialGeneration = 0;
  String? _selectedCandidateKey;
  String? _restoredSelectedCandidateKey;
  int _detailReturnRevision = 0;
  late Stream<StoredProjection?> _spatialStream;
  late Stream<DiscoverySourceState> _sourceStream;

  void _bindStreams() {
    _spatialStream = widget.repository.watchSpatial(_query);
    _sourceStream = widget.repository.watchSource(
      widget.repository.itemsSource(_query),
    );
  }

  @override
  void initState() {
    super.initState();
    _query = widget.query.copyWith(page: 1, clearContinuation: true);
    _visit = discoveryMapVisitState(widget.repository, _query.mapFingerprint);
    widget.repository.rememberExploration(_query);
    _restoredSelectedCandidateKey =
        widget.initialSelectedCandidateKey ?? _visit.selectedCandidateKey;
    _selectedCandidateKey = _restoredSelectedCandidateKey;
    _visit.selectedCandidateKey = _selectedCandidateKey;
    if (_visit.focusedAnchor?.candidateKey != _selectedCandidateKey) {
      _visit.focusedAnchor = null;
    }
    _bindStreams();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant DiscoveryMapScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.query.fingerprint != widget.query.fingerprint ||
        oldWidget.repository != widget.repository) {
      ++_spatialGeneration;
      _refreshing = false;
      _refreshingQuery = null;
      _query = widget.query.copyWith(page: 1, clearContinuation: true);
      _visit = discoveryMapVisitState(widget.repository, _query.mapFingerprint);
      widget.repository.rememberExploration(_query);
      _restoredSelectedCandidateKey =
          widget.initialSelectedCandidateKey ?? _visit.selectedCandidateKey;
      _selectedCandidateKey = _restoredSelectedCandidateKey;
      _visit.selectedCandidateKey = _selectedCandidateKey;
      if (_visit.focusedAnchor?.candidateKey != _selectedCandidateKey) {
        _visit.focusedAnchor = null;
      }
      _bindStreams();
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() async {
    final current = _query;
    try {
      final local = await widget.repository.readSpatial(current);
      // Cached map points render while owner validity is rechecked.
      // This also protects a fresh-looking snapshot after a cold start.
      if (local != null && local.payload['results'] is! List) {
        throw const FormatException('Invalid cached spatial presentation');
      }
      if (mounted && identical(current, _query)) await _refresh();
    } on Object {
      // A missing field is a recoverable source failure, not an empty map.
      if (mounted && identical(current, _query)) await _refresh();
    }
  }

  Future<void> _refresh({bool force = false}) async {
    if (!mounted || (_refreshing && identical(_refreshingQuery, _query))) {
      return;
    }
    final current = _query;
    final repository = widget.repository;
    final generation = ++_spatialGeneration;
    setState(() {
      _refreshing = true;
      _refreshingQuery = current;
    });
    try {
      if (force) {
        await repository.refreshItems(current);
      } else {
        await repository.refreshSpatial(current);
      }
      // One Discovery field provides both N1 and spatial presentation.
    } on Object {
      // An offline field remains readable; no fabricated geographic points.
    } finally {
      if (mounted && generation == _spatialGeneration) {
        setState(() {
          _refreshing = false;
          _refreshingQuery = null;
        });
      }
    }
  }

  Future<DiscoveryItemPresentation?> _verifiedMapDetail(
    DiscoveryItemPresentation candidate,
  ) async {
    final current = _query;
    // A Space map cannot acquire a personal N3 authority as a shortcut.
    // Its published N1/map facts remain visible without this owner fetch.
    if (current.isSpace) return null;
    final startedAt = DateTime.now().toUtc();
    try {
      // A fully projected item from N1 or another Carte view is already
      // available. Merely selecting it is not a fresh authority operation.
      if (await widget.repository.hasReusableItem(
        candidate.family,
        candidate.id,
      )) {
        final cached = await widget.repository.readItem(
          candidate.family,
          candidate.id,
        );
        final local = _selector.detail(cached);
        if (mounted &&
            identical(current, _query) &&
            local?.candidateKey == candidate.candidateKey) {
          return local;
        }
      }
      await widget.repository.refreshItem(candidate.family, candidate.id);
      final source = await widget.repository.readSource(
        widget.repository.itemSource(candidate.family, candidate.id),
      );
      if (source.lastErrorCode != null ||
          source.lastSuccessAt == null ||
          source.lastSuccessAt!.isBefore(startedAt) ||
          source.invalidated ||
          !mounted ||
          !identical(current, _query)) {
        return null;
      }
      final snapshot = await widget.repository.readItem(
        candidate.family,
        candidate.id,
      );
      final detail = _selector.detail(snapshot);
      return detail?.candidateKey == candidate.candidateKey ? detail : null;
    } on Object {
      // No owner-confirmed action is exposed from a stale map projection.
      return null;
    }
  }

  Future<void> _searchPlaceOnMap() async {
    final gateway = widget.geoSearch;
    if (gateway == null) {
      // Existing generic search remains available without a geo provider.
      if (mounted) {
        context.push(_query.routeLocation('/discover/search'));
      }
      return;
    }
    final place = await chooseDiscoveryMapPlace(context, gateway: gateway);
    if (!mounted || place == null) return;
    if (!place.latitude.isFinite ||
        !place.longitude.isFinite ||
        place.latitude < -90 ||
        place.latitude > 90 ||
        place.longitude < -180 ||
        place.longitude > 180) {
      return;
    }
    // A selected geocoder location is an ephemeral search center, not a
    // canonical Makolo Place. Reuse the same Discovery query and spatial
    // projection, constrained to opportunities in its vicinity.
    final query = _query
        .copyWith(clearLocation: true)
        .copyWith(
          place: '',
          latitude: place.latitude,
          longitude: place.longitude,
          radiusKm: 25,
          page: 1,
          clearContinuation: true,
        );
    context.replace(query.routeLocation('/discover/map'));
  }

  Future<void> _openDetail(DiscoveryItemPresentation item) async {
    final open = widget.onOpenItem;
    if (open == null) {
      if (item.occurrenceId != null) {
        widget.onOpenOccurrence(item.occurrenceId!);
      }
      return;
    }
    final query = _query;
    try {
      await open(item.family, item.id);
    } finally {
      // Returning from any owner depth leaves the map's viewport and spatial
      // collection intact. Reconcile only the selected item's owner actions.
      if (mounted &&
          identical(_query, query) &&
          _selectedCandidateKey == item.candidateKey) {
        setState(() => ++_detailReturnRevision);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          StreamBuilder<StoredProjection?>(
            stream: _spatialStream,
            builder: (context, snapshot) {
              return StreamBuilder<DiscoverySourceState>(
                stream: _sourceStream,
                initialData: DiscoverySourceState.unknown,
                builder: (context, sourceSnapshot) {
                  final source =
                      sourceSnapshot.data ?? DiscoverySourceState.unknown;
                  if (!_refreshing &&
                      snapshot.connectionState != ConnectionState.waiting &&
                      snapshot.data == null &&
                      (source.lastSuccessAt != null ||
                          source.lastErrorCode != null ||
                          snapshot.hasError)) {
                    return Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 320),
                        child: Card(
                          child: Padding(
                            padding: const EdgeInsets.all(MakoloSpacing.md),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Text(
                                  'Impossible d’afficher les résultats pour le moment.',
                                  textAlign: TextAlign.center,
                                ),
                                TextButton.icon(
                                  onPressed: () =>
                                      unawaited(_refresh(force: true)),
                                  icon: const Icon(Icons.refresh_rounded),
                                  label: const Text('Réessayer'),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    );
                  }
                  final selection = _selector.spatialSelection(
                    projection: snapshot.data,
                    refreshing: _refreshing,
                    reachability:
                        source.reachability == ReachabilityState.unreachable
                        ? MakoloReachabilityCue.temporarilyUnavailable
                        : source.lastSuccessAt != null
                        ? MakoloReachabilityCue.reachable
                        : MakoloReachabilityCue.unknown,
                    failure:
                        source.lastErrorCode != null ||
                            snapshot.hasError ||
                            sourceSnapshot.hasError
                        ? MakoloFailureCue.recoverable
                        : MakoloFailureCue.none,
                  );
                  return DiscoverySpatialView(
                    key: ValueKey(
                      'discover-map-field-${_query.mapFingerprint}',
                    ),
                    selection: selection,
                    mapConfig: widget.mapConfig,
                    location: widget.location,
                    initialMapFocus:
                        _query.latitude != null && _query.longitude != null
                        ? MapCoordinate(_query.latitude!, _query.longitude!)
                        : null,
                    onDirections: (anchor) => unawaited(
                      showDiscoveryDirections(
                        context,
                        latitude: anchor.latitude,
                        longitude: anchor.longitude,
                      ),
                    ),
                    showMapOnCompact: true,
                    fieldKey: _query.mapFingerprint,
                    initialSelectedCandidateKey: _restoredSelectedCandidateKey,
                    initialFocusedAnchor: _visit.focusedAnchor,
                    detailRefreshRevision: _detailReturnRevision,
                    restoredViewport: _visit.viewport,
                    onViewportChanged: (viewport) {
                      _visit.viewport = viewport;
                    },
                    spatialRevision: snapshot.data?.receivedAt,
                    onSelectionChanged: (key) {
                      _selectedCandidateKey = key;
                      _visit.selectedCandidateKey = key;
                      if (key == null ||
                          _visit.focusedAnchor?.candidateKey != key) {
                        _visit.focusedAnchor = null;
                      }
                    },
                    onFocusedAnchorChanged: (anchor) {
                      _visit.focusedAnchor = anchor;
                    },
                    resolveItem: _verifiedMapDetail,
                    // Same Save owner flow as Découvrir N1. An admitted location
                    // never creates its own saved state or mutation path.
                    onSave: widget.authenticated && !_query.isSpace
                        ? (item) => _saveDiscoveryPossibility(
                            widget.repository,
                            item,
                            _query,
                          )
                        : null,
                    collectiveReadOnly: _query.isSpace,
                    allowOwnerActions:
                        !_query.isSpace &&
                        !_refreshing &&
                        source.lastSuccessAt != null &&
                        source.lastErrorCode == null &&
                        !source.invalidated,
                    baseUri: widget.repository.api.baseUri,
                    shareApi: _query.isSpace ? null : widget.repository.api,
                    shareAuthenticated: widget.authenticated && !_query.isSpace,
                    onRetry: () => unawaited(_refresh(force: true)),
                    onOpen: (item) => unawaited(_openDetail(item)),
                  );
                },
              );
            },
          ),
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.all(MakoloSpacing.sm),
                child: Material(
                  elevation: 2,
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(28),
                  child: Row(
                    children: [
                      IconButton(
                        tooltip: 'Retour à Découvrir',
                        onPressed: () => context.pop(),
                        icon: const Icon(Icons.arrow_back_rounded),
                      ),
                      Expanded(
                        child: Text(
                          _query.latitude == null
                              ? 'Carte'
                              : 'Carte · autour du lieu',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (_query.latitude != null)
                        IconButton(
                          key: const Key('discover-map-clear-place'),
                          tooltip: 'Retirer la zone recherchée',
                          onPressed: () {
                            final next = _query.copyWith(
                              clearLocation: true,
                              place: '',
                              page: 1,
                              clearContinuation: true,
                            );
                            context.replace(
                              next.routeLocation('/discover/map'),
                            );
                          },
                          icon: const Icon(Icons.close_rounded),
                        ),
                      IconButton(
                        key: const Key('discover-map-open-place-search'),
                        tooltip: 'Chercher un lieu',
                        onPressed: () => unawaited(_searchPlaceOnMap()),
                        icon: const Icon(Icons.place_outlined),
                      ),
                      IconButton(
                        key: const Key('discover-map-open-search'),
                        tooltip: 'Rechercher des possibilités',
                        onPressed: () => context.push(
                          _query.routeLocation(
                            '/discover/search',
                            selectedCandidateKey: _selectedCandidateKey,
                          ),
                        ),
                        icon: const Icon(Icons.tune_rounded),
                      ),
                      IconButton(
                        tooltip: 'Actualiser',
                        onPressed: _refreshing ? null : _refresh,
                        icon: const Icon(Icons.refresh_rounded),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
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
    this.actorQuery = const DiscoveryQuery(),
    this.authenticated = false,
  });

  final String family;
  final String id;
  final bool authenticated;
  final DiscoveryQuery actorQuery;
  final DiscoveryRepository repository;

  @override
  State<DiscoveryItemDetailScreen> createState() =>
      _DiscoveryItemDetailScreenState();
}

class _DiscoveryItemDetailScreenState extends State<DiscoveryItemDetailScreen> {
  static const _selector = DiscoverySelector();
  bool _refreshing = false;
  bool _saving = false;
  String? _verifiedItemKey;
  String? _refreshingItemKey;
  int _generation = 0;
  late Stream<DiscoverySourceState> _ownerStream;
  late Stream<StoredProjection?> _itemStream;

  void _bindSources() {
    _ownerStream = widget.repository.watchSource(
      widget.repository.itemSource(
        widget.family,
        widget.id,
        actorQuery: widget.actorQuery,
      ),
    );
    _itemStream = widget.repository.watchItem(
      widget.family,
      widget.id,
      actorQuery: widget.actorQuery,
    );
  }

  String get _itemKey =>
      '${widget.actorQuery.spaceId ?? 'personal'}:${widget.family}:${widget.id}';

  @override
  void initState() {
    super.initState();
    _bindSources();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant DiscoveryItemDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.family != widget.family ||
        oldWidget.id != widget.id ||
        oldWidget.actorQuery.spaceId != widget.actorQuery.spaceId ||
        oldWidget.repository != widget.repository) {
      // A detail for another family/resource may never inherit N2 authority.
      ++_generation;
      _refreshing = false;
      _saving = false;
      _verifiedItemKey = null;
      _refreshingItemKey = null;
      _bindSources();
      unawaited(_acquire());
    }
  }

  @override
  void dispose() {
    ++_generation;
    super.dispose();
  }

  Future<void> _acquire() async {
    final key = _itemKey;
    final repository = widget.repository;
    final source = widget.repository.itemSource(
      widget.family,
      widget.id,
      actorQuery: widget.actorQuery,
    );
    final state = await widget.repository.readSource(source);
    // First materialize admitted N1 facts into the same actor-scoped N3
    // snapshot. Offline reading is allowed; actions still require owner
    // verification by a successful detail response.
    await repository.readItem(
      widget.family,
      widget.id,
      actorQuery: widget.actorQuery,
    );
    final reusable =
        state.lastSuccessAt != null &&
        !state.invalidated &&
        state.lastErrorCode == null &&
        await repository.hasReusableItem(
          widget.family,
          widget.id,
          actorQuery: widget.actorQuery,
        );
    if (!mounted ||
        key != _itemKey ||
        !identical(repository, widget.repository)) {
      return;
    }
    if (reusable) {
      setState(() => _verifiedItemKey = key);
      return;
    }
    await _refresh();
  }

  Future<void> _refresh() async {
    final key = _itemKey;
    if (_refreshing && _refreshingItemKey == key) return;
    final generation = ++_generation;
    final family = widget.family;
    final id = widget.id;
    final startedAt = DateTime.now().toUtc();
    setState(() {
      _refreshing = true;
      _refreshingItemKey = key;
      _verifiedItemKey = null;
    });
    try {
      await widget.repository.refreshItem(
        family,
        id,
        actorQuery: widget.actorQuery,
      );
      final state = await widget.repository.readSource(
        widget.repository.itemSource(family, id, actorQuery: widget.actorQuery),
      );
      if (!mounted || generation != _generation || key != _itemKey) return;
      if (state.lastErrorCode == null &&
          state.lastSuccessAt != null &&
          !state.lastSuccessAt!.isBefore(startedAt) &&
          !state.invalidated) {
        // The owner confirmed the current item, not merely a success stamp.
        final projection = await widget.repository.readItem(
          family,
          id,
          actorQuery: widget.actorQuery,
        );
        final detail = _selector.detail(projection);
        if (mounted &&
            generation == _generation &&
            key == _itemKey &&
            detail?.family == family &&
            detail?.id == id) {
          setState(() => _verifiedItemKey = key);
        }
      }
    } on Object {
      // Preserve valid cached facts without granting owner actions.
    } finally {
      if (mounted && generation == _generation && key == _itemKey) {
        setState(() {
          _refreshing = false;
          _refreshingItemKey = null;
        });
      }
    }
  }

  Future<void> _setSaved(bool saved) async {
    final key = _itemKey;
    if (!widget.authenticated ||
        widget.actorQuery.isSpace ||
        _saving ||
        _refreshing ||
        _verifiedItemKey != key) {
      return;
    }
    final family = widget.family;
    final id = widget.id;
    setState(() => _saving = true);
    try {
      // No optimistic mutation: the Discovery owner returns a confirmed item.
      await widget.repository.setSaved(family: family, id: id, saved: saved);
    } on Object {
      if (mounted && key == _itemKey) {
        await _refresh();
        if (mounted && key == _itemKey) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Modification non confirmée. Actualisez avant de réessayer.',
              ),
            ),
          );
        }
      }
    } finally {
      if (mounted && key == _itemKey) setState(() => _saving = false);
    }
  }

  Future<void> _openOwnerDepth(
    String path, {
    required bool mayChangeOwnerState,
  }) async {
    final key = _itemKey;
    final repository = widget.repository;
    final family = widget.family;
    final id = widget.id;
    try {
      await context.push<void>(path);
    } finally {
      if (mounted &&
          key == _itemKey &&
          identical(repository, widget.repository)) {
        // A read-only N3 is a presentation, not an owner mutation.
        // Action routes may change capabilities, so always revalidate them.
        bool needsRefresh = mayChangeOwnerState;
        if (!needsRefresh) {
          try {
            needsRefresh = !await repository.hasReusableItem(
              family,
              id,
              actorQuery: widget.actorQuery,
            );
          } on Object {
            needsRefresh = true;
          }
        }
        if (needsRefresh &&
            mounted &&
            key == _itemKey &&
            identical(repository, widget.repository)) {
          await _refresh();
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<DiscoverySourceState>(
      key: ValueKey('discover-n2-owner-$_itemKey'),
      stream: _ownerStream,
      initialData: DiscoverySourceState.unknown,
      builder: (context, ownerSnapshot) {
        final owner = ownerSnapshot.data ?? DiscoverySourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: _itemStream,
          builder: (context, snapshot) {
            DiscoveryItemPresentation? item;
            var incompatible = false;
            try {
              item = _selector.detail(snapshot.data);
            } on FormatException {
              incompatible = true;
            }
            final verified =
                !_refreshing &&
                !_saving &&
                _verifiedItemKey == _itemKey &&
                item != null &&
                owner.lastErrorCode == null &&
                !owner.invalidated;
            final vertical = item?.representation?['vertical_label'];
            final title = vertical is String && vertical.trim().isNotEmpty
                ? vertical.trim()
                : 'Possibilité';

            return Scaffold(
              appBar: AppBar(
                title: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
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
                            message: owner.ownerUnavailable
                                ? 'Cette possibilité n’est plus accessible.'
                                : incompatible
                                ? 'La réponse de cette possibilité est incompatible.'
                                : owner.lastErrorCode != null
                                ? 'Impossible de charger cette possibilité. Réessayez.'
                                : 'Ce contenu n’est pas disponible.',
                            onRetry: _refresh,
                          )
                  : ListView(
                      key: Key(
                        widget.actorQuery.isSpace
                            ? 'discover-space-n3'
                            : 'discover-personal-n2',
                      ),
                      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                      children: [
                        Center(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 1040),
                            child: DiscoveryPossibilityUnit(
                              key: ValueKey('discover-n2-unit-$_itemKey'),
                              item: item,
                              profileId: widget.repository.profileId,
                              allowOwnerActions:
                                  verified && !widget.actorQuery.isSpace,
                              collectiveReadOnly: widget.actorQuery.isSpace,
                              detailMode: true,
                              onOpen: () {},
                              onNativeAction: widget.actorQuery.isSpace
                                  ? null
                                  : (path) => unawaited(
                                      _openOwnerDepth(
                                        path,
                                        mayChangeOwnerState: true,
                                      ),
                                    ),
                              onOwnerDepth: widget.actorQuery.isSpace
                                  ? null
                                  : (path) => unawaited(
                                      _openOwnerDepth(
                                        path,
                                        mayChangeOwnerState: false,
                                      ),
                                    ),
                              onSave:
                                  widget.authenticated &&
                                      !widget.actorQuery.isSpace &&
                                      verified &&
                                      !_saving &&
                                      (item.savedState == 'saved'
                                          ? item.canUnsave
                                          : item.canSave)
                                  ? () => _setSaved(item!.savedState != 'saved')
                                  : null,
                              shareApi: widget.actorQuery.isSpace
                                  ? null
                                  : widget.repository.api,
                              shareAuthenticated:
                                  widget.authenticated &&
                                  !widget.actorQuery.isSpace,
                              baseUri: widget.repository.api.baseUri,
                            ),
                          ),
                        ),
                        if (!widget.actorQuery.isSpace &&
                            verified &&
                            item.wire['journey_continuation'] is Map &&
                            const {'active', 'finished'}.contains(
                              (item.wire['journey_continuation']
                                  as Map)['state'],
                            ))
                          Builder(
                            builder: (context) {
                              final continuation =
                                  item!.wire['journey_continuation'] as Map;
                              final resource = continuation['resource'];
                              final links = continuation['links'];
                              final journeyId =
                                  resource is Map &&
                                      resource['kind'] == 'journey'
                                  ? resource['id']
                                  : null;
                              final path = links is Map
                                  ? links['native']
                                  : null;
                              if (journeyId is! String ||
                                  journeyId.isEmpty ||
                                  path != '/journeys/$journeyId') {
                                return const SizedBox.shrink();
                              }
                              // An existing owner "continue" action already
                              // opens the canonical Journey: never show two
                              // buttons for the same handoff.
                              final primary =
                                  item.engagement?['primary_action'];
                              final destination = primary is Map
                                  ? primary['destination']
                                  : null;
                              if (destination is Map &&
                                  primary is Map &&
                                  primary['code'] == 'continue' &&
                                  destination['kind'] == 'native' &&
                                  destination['path'] == path) {
                                return const SizedBox.shrink();
                              }
                              return Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: MakoloSpacing.md,
                                  vertical: MakoloSpacing.sm,
                                ),
                                child: MakoloActionButton(
                                  key: const Key('discover-n3-resume-journey'),
                                  onPressed: () => unawaited(
                                    _openOwnerDepth(
                                      path,
                                      mayChangeOwnerState: true,
                                    ),
                                  ),
                                  label: continuation['state'] == 'active'
                                      ? 'Reprendre ma démarche'
                                      : 'Voir ma démarche',
                                  appearance: MakoloActionAppearance.primary,
                                  icon: Icons.route_outlined,
                                ),
                              );
                            },
                          ),
                        if (discoveryDirectionsDestinations(item).isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: MakoloSpacing.md,
                            ),
                            child: OutlinedButton.icon(
                              key: const Key('discover-n2-directions'),
                              onPressed: () => unawaited(
                                showDiscoveryItemDirections(context, item!),
                              ),
                              icon: const Icon(Icons.directions_outlined),
                              label: const Text('Itinéraire'),
                            ),
                          ),
                      ],
                    ),
            );
          },
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
    this.conversations,
    this.onOpenConversation,
  });

  final String activityId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenOccurrence;
  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;

  @override
  State<ActivityDetailScreen> createState() => _ActivityDetailScreenState();
}

class _ActivityDetailScreenState extends State<ActivityDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;
  int _generation = 0;
  String? _knownSavedTitle;
  late Stream<DiscoverySourceState> _ownerStream;
  late Stream<StoredProjection?> _previewStream;
  late Stream<StoredProjection?> _detailStream;

  void _bindStreams() {
    _ownerStream = widget.repository.watchSource(
      widget.repository.activitySource(widget.activityId),
    );
    _previewStream = widget.repository.watchActivityPreview(widget.activityId);
    _detailStream = widget.repository.watchActivity(widget.activityId);
  }

  @override
  void initState() {
    super.initState();
    _bindStreams();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant ActivityDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.activityId != widget.activityId ||
        oldWidget.repository != widget.repository) {
      _knownSavedTitle = null;
      _refreshing = false;
      ++_generation;
      _bindStreams();
      unawaited(_acquire());
    }
  }

  @override
  void dispose() {
    ++_generation;
    super.dispose();
  }

  Future<void> _acquire() async {
    // Reuse an already acquired full Activity projection for reading.
    // A private owner decision or a live action still checks its own API.
    final id = widget.activityId;
    final repository = widget.repository;
    unawaited(_readKnownSavedTitle(id));
    if (await repository.hasReusableActivity(id)) return;
    if (mounted &&
        widget.activityId == id &&
        identical(repository, widget.repository)) {
      await _refresh();
    }
  }

  Future<void> _readKnownSavedTitle(String requestedId) async {
    final repository = widget.repository;
    try {
      final root = await repository.store.readProjection('personal.me');
      final actor = root?.payload['actor'];
      if (actor is! Map ||
          actor['type'] != 'profile' ||
          actor['id']?.toString() != repository.store.profileId) {
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
            widget.activityId == requestedId &&
            identical(widget.repository, repository)) {
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
    final repository = widget.repository;
    final generation = ++_generation;
    setState(() => _refreshing = true);
    try {
      // Always revalidate N3 on entry even when an N1 preview exists.
      await repository.refreshActivity(requestedId);
      final source = await repository.readSource(
        repository.activitySource(requestedId),
      );
      if (source.ownerUnavailable &&
          mounted &&
          generation == _generation &&
          identical(widget.repository, repository) &&
          widget.activityId == requestedId) {
        setState(() => _knownSavedTitle = null);
      }
    } on Object {
      // The owner source records errors and discards revoked keyed details.
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _refreshing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<DiscoverySourceState>(
      stream: _ownerStream,
      initialData: DiscoverySourceState.unknown,
      builder: (context, ownerSnapshot) {
        final owner = ownerSnapshot.data ?? DiscoverySourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: _previewStream,
          builder: (context, previewSnapshot) {
            return StreamBuilder<StoredProjection?>(
              stream: _detailStream,
              builder: (context, snapshot) {
                final id = snapshot.data?.payload['identity'];
                final valid =
                    id is Map &&
                    id['kind'] == 'activity' &&
                    id['id'] == widget.activityId;
                final activity = owner.ownerUnavailable
                    ? null
                    : (valid ? _selector.activity(snapshot.data) : null) ??
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
                    child: owner.ownerUnavailable
                        ? MakoloErrorState(
                            message: 'Cette activité n’est plus accessible.',
                            onRetry: _refresh,
                          )
                        : activity == null
                        ? _knownSavedTitle != null
                              ? ListView(
                                  children: [
                                    MakoloDetailHeader(
                                      title: _knownSavedTitle!,
                                    ),
                                  ],
                                )
                              : _refreshing
                              ? const MakoloLoadingState(label: 'Mise à jour…')
                              : MakoloErrorState(
                                  message:
                                      'Cette activité n’est pas disponible.',
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
                              if (widget.conversations != null &&
                                  widget.onOpenConversation != null)
                                ConversationContextAction(
                                  repository: widget.conversations!,
                                  kind: 'activity',
                                  contextId: widget.activityId,
                                  onOpen: widget.onOpenConversation!,
                                ),
                              if (activity.occurrences.isNotEmpty)
                                MakoloSection(
                                  title: switch (activity.occurrenceNoun) {
                                    'Départ' => 'Départs',
                                    'Date' => 'Dates',
                                    'Créneau' => 'Créneaux',
                                    'Session' => 'Sessions',
                                    _ => 'Dates et réalisations',
                                  },
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
                                            title: activity
                                                .occurrences[index]
                                                .label,
                                            status:
                                                activity
                                                        .occurrences[index]
                                                        .state ==
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
                                        if (index <
                                            activity.occurrences.length - 1)
                                          const SizedBox(
                                            height: MakoloSpacing.sm,
                                          ),
                                      ],
                                      if (activity.occurrencesHasMore)
                                        Padding(
                                          key: const Key(
                                            'discover-n3-occurrences-limited',
                                          ),
                                          padding: const EdgeInsets.only(
                                            top: MakoloSpacing.sm,
                                          ),
                                          child: Text(
                                            'D’autres réalisations existent. Cette page '
                                            'présente uniquement celles communiquées '
                                            'dans le détail actuel.',
                                            style: Theme.of(context)
                                                .textTheme
                                                .bodySmall,
                                          ),
                                        ),
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
    this.conversations,
    this.onOpenConversation,
  });

  final String occurrenceId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final VoidCallback? onOpenDayOf;
  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;

  @override
  State<OccurrenceDetailScreen> createState() => _OccurrenceDetailScreenState();
}

class _OccurrenceDetailScreenState extends State<OccurrenceDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;
  bool _verifiedOwner = false;
  bool _dayOfAuthorized = false;
  int _generation = 0;
  late Stream<DiscoverySourceState> _ownerStream;
  late Stream<StoredProjection?> _previewStream;
  late Stream<StoredProjection?> _detailStream;

  void _bindStreams() {
    _ownerStream = widget.repository.watchSource(
      widget.repository.occurrenceSource(widget.occurrenceId),
    );
    _previewStream = widget.repository.watchOccurrencePreview(
      widget.occurrenceId,
    );
    _detailStream = widget.repository.watchOccurrence(widget.occurrenceId);
  }

  @override
  void initState() {
    super.initState();
    _bindStreams();
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant OccurrenceDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.occurrenceId != widget.occurrenceId ||
        oldWidget.repository != widget.repository) {
      _verifiedOwner = false;
      _dayOfAuthorized = false;
      _refreshing = false;
      ++_generation;
      _bindStreams();
      unawaited(_acquire());
    }
  }

  Future<void> _acquire() async {
    final id = widget.occurrenceId;
    final repository = widget.repository;
    if (await repository.hasReusableOccurrenceForReading(id)) return;
    if (mounted &&
        widget.occurrenceId == id &&
        identical(repository, widget.repository)) {
      await _refresh();
    }
  }

  @override
  void dispose() {
    ++_generation;
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final requestedId = widget.occurrenceId;
    final generation = ++_generation;
    final startedAt = DateTime.now().toUtc();
    setState(() {
      _refreshing = true;
      _verifiedOwner = false;
      _dayOfAuthorized = false;
    });
    try {
      await widget.repository.refreshOccurrence(requestedId);
      final source = await widget.repository.readSource(
        widget.repository.occurrenceSource(requestedId),
      );
      if (!mounted ||
          generation != _generation ||
          widget.occurrenceId != requestedId) {
        return;
      }
      if (source.lastErrorCode == null &&
          source.lastSuccessAt != null &&
          !source.lastSuccessAt!.isBefore(startedAt) &&
          !source.invalidated) {
        final snapshot = await widget.repository.readOccurrence(requestedId);
        final identity = snapshot?.payload['identity'];
        if (mounted &&
            generation == _generation &&
            widget.occurrenceId == requestedId &&
            identity is Map &&
            identity['kind'] == 'occurrence' &&
            identity['id'] == requestedId) {
          final capabilities = snapshot?.payload['capabilities'];
          setState(() {
            _verifiedOwner = true;
            _dayOfAuthorized =
                capabilities is List && capabilities.contains('open_day_of');
          });
        }
      }
    } on Object {
      // Keep known facts readable, never reuse an old live/Day-Of right.
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _refreshing = false);
      }
      if (mounted && !_refreshing && widget.occurrenceId != requestedId) {
        unawaited(_refresh());
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<DiscoverySourceState>(
      stream: _ownerStream,
      initialData: DiscoverySourceState.unknown,
      builder: (context, ownerSnapshot) {
        final owner = ownerSnapshot.data ?? DiscoverySourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: _previewStream,
          builder: (context, previewSnapshot) {
            return StreamBuilder<StoredProjection?>(
              stream: _detailStream,
              builder: (context, snapshot) {
                final identity = snapshot.data?.payload['identity'];
                final ownerIdentityValid =
                    identity is Map &&
                    identity['kind'] == 'occurrence' &&
                    identity['id'] == widget.occurrenceId;
                final occurrence = owner.ownerUnavailable
                    ? null
                    : (ownerIdentityValid
                              ? _selector.occurrence(snapshot.data)
                              : null) ??
                          _selector.occurrencePreview(previewSnapshot.data);
                final dayOfVerified =
                    _verifiedOwner &&
                    _dayOfAuthorized &&
                    !_refreshing &&
                    owner.lastErrorCode == null &&
                    !owner.invalidated;
                return Scaffold(
                  appBar: AppBar(
                    title: Text(
                      occurrence?.noun ?? 'Réalisation',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
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
                                  message: owner.ownerUnavailable
                                      ? 'Cette réalisation n’est plus accessible.'
                                      : 'Cette réalisation n’est pas disponible.',
                                  onRetry: _refresh,
                                )
                        : ListView(
                            padding: const EdgeInsets.only(
                              bottom: MakoloSpacing.xl,
                            ),
                            children: [
                              MakoloDetailHeader(
                                eyebrow: occurrence.noun ?? 'Réalisation',
                                title: occurrence.activityTitle,
                                status: occurrence.state == null
                                    ? null
                                    : MakoloStatus(label: occurrence.state!),
                                metadata: [
                                  if (occurrence.timing != null)
                                    MakoloMetadataItem(
                                      'Début : ${occurrence.timing!}',
                                      icon: Icons.schedule_outlined,
                                    ),
                                  if (occurrence.endTiming != null)
                                    MakoloMetadataItem(
                                      'Fin : ${occurrence.endTiming!}',
                                      icon: Icons.event_outlined,
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
                              if (widget.conversations != null &&
                                  widget.onOpenConversation != null)
                                ConversationContextAction(
                                  repository: widget.conversations!,
                                  kind: 'occurrence',
                                  contextId: widget.occurrenceId,
                                  onOpen: widget.onOpenConversation!,
                                ),
                              Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: MakoloSpacing.inner,
                                ),
                                child: OutlinedButton.icon(
                                  onPressed: () => widget.onOpenActivity(
                                    occurrence.activityId,
                                  ),
                                  icon: const Icon(Icons.arrow_back_rounded),
                                  label: const Text('Voir l’activité'),
                                ),
                              ),
                              if (dayOfVerified && occurrence.canOpenDayOf)
                                Padding(
                                  padding: const EdgeInsets.fromLTRB(
                                    MakoloSpacing.inner,
                                    MakoloSpacing.md,
                                    MakoloSpacing.inner,
                                    0,
                                  ),
                                  child: MakoloAttentionBlock(
                                    title: 'Jour J disponible',
                                    body: 'Consultez les informations pratiques pour le Jour J.',
                                    icon: Icons.directions_walk_rounded,
                                    action: widget.onOpenDayOf == null
                                        ? null
                                        : FilledButton.icon(
                                            onPressed: widget.onOpenDayOf,
                                            icon: const Icon(
                                              Icons.directions_walk_rounded,
                                            ),
                                            label: const Text(
                                              'Ouvrir le Jour J',
                                            ),
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
      },
    );
  }
}
