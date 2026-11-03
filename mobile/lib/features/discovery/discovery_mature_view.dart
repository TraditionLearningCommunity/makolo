import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/presentation_media.dart';
import '../../design/surface_states.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/maps/makolo_map_view.dart';
import '../../platform/maps/map_runtime_config.dart';
import '../../platform/maps/discovery_map_controller.dart';
import '../../network/makolo_api_client.dart';
import '../../presentation/search/load_more_on_scroll.dart';
import '../../presentation/media/retained_public_discovery_image.dart';
import '../../presentation/possibilities/discovery_offline_store.dart';
import '../../presentation/possibilities/discovery_possibility_unit.dart';
import 'discovery_selector.dart';
import 'discovery_share_sheet.dart';

typedef DiscoveryOpenItem = void Function(DiscoveryItemPresentation item);
typedef DiscoverySaveItem = Future<void> Function(
  DiscoveryItemPresentation item,
);
typedef DiscoveryResolveItem = Future<DiscoveryItemPresentation?> Function(
  DiscoveryItemPresentation item,
);

class DiscoveryExplorationView extends StatefulWidget {
  const DiscoveryExplorationView({
    super.key,
    required this.selection,
    required this.onOpen,
    this.onSave,
    this.baseUri,
    this.shareApi,
    this.profileId,
    this.allowOwnerActions = true,
    this.onPage,
    this.autoLoadMore = false,
    this.loadingMore = false,
    this.loadMoreFailed = false,
    this.onRetry,
    this.onResetCriteria,
    this.onMap,
    this.onWatch,
    this.fieldKey,
    this.scrollController,
    this.initialFocusedCandidateKey,
    this.onFocusedCandidateChanged,
  });

  final DiscoveryFieldSelection selection;
  final DiscoveryOpenItem onOpen;
  final DiscoverySaveItem? onSave;
  final Uri? baseUri;
  final MakoloApiClient? shareApi;
  final String? profileId;
  final bool allowOwnerActions;
  final ValueChanged<int>? onPage;
  final bool autoLoadMore;
  final bool loadingMore;
  final bool loadMoreFailed;
  final VoidCallback? onRetry;
  final VoidCallback? onResetCriteria;
  final ValueChanged<String?>? onMap;
  final VoidCallback? onWatch;
  final String? fieldKey;
  final ScrollController? scrollController;
  final String? initialFocusedCandidateKey;
  final ValueChanged<String?>? onFocusedCandidateChanged;

  @override
  State<DiscoveryExplorationView> createState() =>
      _DiscoveryExplorationViewState();
}

class _DiscoveryExplorationViewState extends State<DiscoveryExplorationView> {
  String? _focusedCandidateKey;

  @override
  void initState() {
    super.initState();
    _focusedCandidateKey = widget.initialFocusedCandidateKey;
  }

  void _focus(String? candidateKey) {
    setState(() => _focusedCandidateKey = candidateKey);
    widget.onFocusedCandidateChanged?.call(candidateKey);
  }

  @override
  void didUpdateWidget(covariant DiscoveryExplorationView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialFocusedCandidateKey !=
        widget.initialFocusedCandidateKey) {
      _focusedCandidateKey = widget.initialFocusedCandidateKey;
    }
    final keys = widget.selection.collection.items
        .map((item) => item.candidateKey)
        .toSet();
    if (_focusedCandidateKey != null &&
        keys.isNotEmpty &&
        !keys.contains(_focusedCandidateKey)) {
      _focusedCandidateKey = null;
    }
  }

  DiscoveryItemPresentation? get _focusedItem {
    final key = _focusedCandidateKey;
    if (key == null) return null;
    for (final item in widget.selection.collection.items) {
      if (item.candidateKey == key) return item;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.hasBoundedWidth
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        final wide = width >= MakoloLayout.wideMinWidth;
        final focused = _focusedItem;

        if (!wide) {
          return DiscoveryFieldView(
            selection: widget.selection,
            onOpen: widget.onOpen,
            onSave: widget.onSave,
            onWatch: widget.onWatch,
            baseUri: widget.baseUri,
            shareApi: widget.shareApi,
            profileId: widget.profileId,
            allowOwnerActions: widget.allowOwnerActions,
            onPage: widget.onPage,
            autoLoadMore: widget.autoLoadMore,
            loadingMore: widget.loadingMore,
            loadMoreFailed: widget.loadMoreFailed,
            onRetry: widget.onRetry,
            onResetCriteria: widget.onResetCriteria,
            selectedCandidateKey: _focusedCandidateKey,
            onMap: widget.onMap == null
                ? null
                : () => widget.onMap!(
                    focused?.isMappable == true ? _focusedCandidateKey : null,
                  ),
            fieldKey: widget.fieldKey,
            scrollController: widget.scrollController,
          );
        }

        final field = DiscoveryFieldView(
          selection: widget.selection,
          onOpen: widget.onOpen,
          onSave: widget.onSave,
          onWatch: widget.onWatch,
          baseUri: widget.baseUri,
          shareApi: widget.shareApi,
          profileId: widget.profileId,
          allowOwnerActions: widget.allowOwnerActions,
          onPage: widget.onPage,
          autoLoadMore: widget.autoLoadMore,
          loadingMore: widget.loadingMore,
          loadMoreFailed: widget.loadMoreFailed,
          onRetry: widget.onRetry,
          onResetCriteria: widget.onResetCriteria,
          onMap: widget.onMap == null
              ? null
              : () => widget.onMap!(
                  focused?.isMappable == true ? _focusedCandidateKey : null,
                ),
          fieldKey: widget.fieldKey,
          scrollController: widget.scrollController,
          selectedCandidateKey: _focusedCandidateKey,
          onSelect: (item) => _focus(item.candidateKey),
          selectOnCardTap: true,
        );
        if (focused == null) return field;

        return MakoloAdaptiveSplit(
          splitAt: MakoloLayout.wideMinWidth,
          field: field,
          focus: _DiscoveryFocusPane(
            item: focused,
            baseUri: widget.baseUri,
            onClose: () => _focus(null),
            onOpen: () => widget.onOpen(focused),
          ),
          narrow: field,
        );
      },
    );
  }
}

class DiscoveryFieldView extends StatelessWidget {
  const DiscoveryFieldView({
    super.key,
    required this.selection,
    required this.onOpen,
    this.onSave,
    this.baseUri,
    this.shareApi,
    this.profileId,
    this.allowOwnerActions = true,
    this.onPage,
    this.autoLoadMore = false,
    this.loadingMore = false,
    this.loadMoreFailed = false,
    this.onRetry,
    this.onResetCriteria,
    this.selectedCandidateKey,
    this.onSelect,
    this.selectionActionLabel,
    this.selectOnCardTap = false,
    this.onMap,
    this.onWatch,
    this.fieldKey,
    this.scrollController,
  });

  final DiscoveryFieldSelection selection;
  final DiscoveryOpenItem onOpen;
  final DiscoverySaveItem? onSave;
  final Uri? baseUri;
  final MakoloApiClient? shareApi;
  final String? profileId;
  final bool allowOwnerActions;
  final ValueChanged<int>? onPage;
  final bool autoLoadMore;
  final bool loadingMore;
  final bool loadMoreFailed;
  final VoidCallback? onRetry;
  final VoidCallback? onResetCriteria;
  final String? selectedCandidateKey;
  final ValueChanged<DiscoveryItemPresentation>? onSelect;
  final String? selectionActionLabel;
  final bool selectOnCardTap;
  final VoidCallback? onMap;
  final VoidCallback? onWatch;
  final String? fieldKey;
  final ScrollController? scrollController;

  @override
  Widget build(BuildContext context) {
    return MakoloSurfaceStateView(
      state: selection.surface,
      blockingErrorMessage: 'Ce contenu n’est pas disponible.',
      // The connectivity cue is already shown by the shell. Keep usable
      // cached possibilities visible without a second verbose error notice.
      recoverableErrorMessage: null,
      preservedMessage: null,
      onRetry: onRetry,
      empty: _DiscoveryEmptyState(
        states: selection.states,
        onRetry: onRetry,
        onResetCriteria: onResetCriteria,
      ),
      content: _DiscoveryScrollableField(
        selection: selection,
        onOpen: onOpen,
        onSave: onSave,
        baseUri: baseUri,
        shareApi: shareApi,
        profileId: profileId,
        allowOwnerActions: allowOwnerActions,
        onPage: onPage,
        autoLoadMore: autoLoadMore,
        loadingMore: loadingMore,
        loadMoreFailed: loadMoreFailed,
        selectedCandidateKey: selectedCandidateKey,
        onSelect: onSelect,
        selectionActionLabel: selectionActionLabel,
        selectOnCardTap: selectOnCardTap,
        onMap: onMap,
        onWatch: onWatch,
        fieldKey: fieldKey,
        scrollController: scrollController,
      ),
    );
  }
}

/// A bounded choice of distinct possibilities sharing a rendered coordinate.
/// It does not treat coordinate equality as proof of one canonical Place.
class DiscoveryCoLocatedPicker extends StatefulWidget {
  const DiscoveryCoLocatedPicker({
    super.key,
    required this.items,
    required this.onChoose,
  });

  final List<DiscoveryItemPresentation> items;
  final ValueChanged<DiscoveryItemPresentation> onChoose;

  @override
  State<DiscoveryCoLocatedPicker> createState() =>
      _DiscoveryCoLocatedPickerState();
}

class _DiscoveryCoLocatedPickerState extends State<DiscoveryCoLocatedPicker> {
  final DraggableScrollableController _sheetController =
      DraggableScrollableController();
  bool _expanded = false;

  @override
  void dispose() {
    _sheetController.dispose();
    super.dispose();
  }

  void _showAll() {
    setState(() => _expanded = true);
    if (_sheetController.isAttached) {
      unawaited(
        _sheetController.animateTo(
          0.76,
          duration: const Duration(milliseconds: 240),
          curve: Curves.easeOutCubic,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = widget.items;
    final place = items.isEmpty ? null : items.first.place;
    final commonPlace = place != null &&
        place.trim().isNotEmpty &&
        items.every((item) => item.place == place);
    final visible = _expanded || items.length <= 2 ? items.length : 2;
    return DraggableScrollableSheet(
      key: const Key('discover-map-colocated-sheet'),
      controller: _sheetController,
      expand: false,
      initialChildSize: 0.40,
      minChildSize: 0.26,
      maxChildSize: 0.78,
      builder: (context, scrollController) => ListView.builder(
        controller: scrollController,
        padding: const EdgeInsets.fromLTRB(
          MakoloSpacing.md,
          MakoloSpacing.sm,
          MakoloSpacing.md,
          MakoloSpacing.xl,
        ),
        itemCount: visible + (_expanded || visible == items.length ? 1 : 2),
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${items.length} possibilités à cet emplacement',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  if (commonPlace)
                    Text(
                      place,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                ],
              ),
            );
          }
          if (index == visible + 1) {
            return TextButton.icon(
              key: const Key('discover-map-colocated-more'),
              onPressed: _showAll,
              icon: const Icon(Icons.expand_more_rounded),
              label: Text('Voir les ${items.length} possibilités'),
            );
          }
          final item = items[index - 1];
          return ListTile(
            key: ValueKey('discover-map-place-choice-${item.candidateKey}'),
            contentPadding: EdgeInsets.zero,
            title: Text(
              item.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: item.place == null
                ? null
                : Text(
                    item.place!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => widget.onChoose(item),
          );
        },
      ),
    );
  }
}

class DiscoverySpatialView extends StatefulWidget {
  const DiscoverySpatialView({
    super.key,
    required this.selection,
    required this.mapConfig,
    required this.onOpen,
    this.location,
    this.onSave,
    this.resolveItem,
    this.baseUri,
    this.shareApi,
    this.profileId,
    this.allowOwnerActions = true,
    this.onPage,
    this.autoLoadMore = false,
    this.loadingMore = false,
    this.loadMoreFailed = false,
    this.onRetry,
    this.initialSelectedCandidateKey,
    this.showMapOnCompact = false,
    this.fieldKey,
    this.onSelectionChanged,
  });

  final DiscoveryFieldSelection selection;
  final MakoloMapsConfig mapConfig;
  final DiscoveryOpenItem onOpen;
  final LocationCapability? location;
  final DiscoverySaveItem? onSave;
  final DiscoveryResolveItem? resolveItem;
  final Uri? baseUri;
  final MakoloApiClient? shareApi;
  final String? profileId;
  final bool allowOwnerActions;
  final ValueChanged<int>? onPage;
  final bool autoLoadMore;
  final bool loadingMore;
  final bool loadMoreFailed;
  final VoidCallback? onRetry;
  final String? initialSelectedCandidateKey;
  final bool showMapOnCompact;
  final String? fieldKey;
  final ValueChanged<String?>? onSelectionChanged;

  @override
  State<DiscoverySpatialView> createState() => _DiscoverySpatialViewState();
}

class _DiscoverySpatialViewState extends State<DiscoverySpatialView> {
  static const _selector = DiscoverySelector();
  String? _selectedCandidateKey;
  DiscoveryMapController? _mapController;
  final Map<Object, String> _circleKeys = {};
  int _pinGeneration = 0;
  bool _initialCameraPositioned = false;
  double? _deviceLatitude;
  double? _deviceLongitude;
  DiscoveryItemPresentation? _confirmedDetail;
  int _detailGeneration = 0;
  bool _savingSelected = false;

  @override
  void dispose() {
    ++_pinGeneration;
    ++_detailGeneration;
    _circleKeys.clear();
    _mapController = null;
    super.dispose();
  }

  void _select(String key, {bool moveCamera = true}) {
    final changed = _selectedCandidateKey != key;
    setState(() {
      _selectedCandidateKey = key;
      if (changed) _confirmedDetail = null;
    });
    widget.onSelectionChanged?.call(key);
    if (changed) unawaited(_resolveSelected());
    if (!moveCamera) return;
    final anchors = _selector.spatialAnchorsFromCollection(
      widget.selection.collection,
    );
    for (final anchor in anchors) {
      if (anchor.candidateKey != key) continue;
      final controller = _mapController;
      if (controller != null) {
        unawaited(_moveCamera(controller, anchor));
      }
      break;
    }
  }

  void _clearSelection() {
    ++_detailGeneration;
    setState(() {
      _selectedCandidateKey = null;
      _confirmedDetail = null;
    });
    widget.onSelectionChanged?.call(null);
  }

  Future<void> _resolveSelected() async {
    final resolver = widget.resolveItem;
    final key = _selectedCandidateKey;
    if (resolver == null || key == null) return;
    final candidates = widget.selection.collection.items
        .where((item) => item.candidateKey == key);
    if (candidates.isEmpty) return;
    final generation = ++_detailGeneration;
    try {
      final detail = await resolver(candidates.first);
      if (!mounted ||
          generation != _detailGeneration ||
          _selectedCandidateKey != key) {
        return;
      }
      setState(() {
        _confirmedDetail = detail?.candidateKey == key ? detail : null;
      });
    } on Object {
      // Unverified detail never unlocks a mutation. The canonical N2
      // remains available and rechecks its own authorization.
      if (mounted && generation == _detailGeneration) {
        setState(() => _confirmedDetail = null);
      }
    }
  }

  Future<void> _saveSelected() async {
    final item = _confirmedDetail;
    final save = widget.onSave;
    if (_savingSelected || item == null || save == null) return;
    if (item.savedState == 'saved' ? !item.canUnsave : !item.canSave) {
      return;
    }
    setState(() => _savingSelected = true);
    try {
      await save(item);
      if (mounted && _selectedCandidateKey == item.candidateKey) {
        await _resolveSelected();
      }
    } on Object {
      if (mounted && _selectedCandidateKey == item.candidateKey) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('L’enregistrement n’a pas pu être confirmé.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _savingSelected = false);
    }
  }

  Future<void> _moveCamera(
    DiscoveryMapController controller,
    DiscoverySpatialAnchor anchor,
  ) async {
    try {
      await controller.moveTo(anchor.latitude, anchor.longitude);
    } on Object {
      // The list selection remains usable while the map is unavailable.
    }
  }

  void _mapCreated(DiscoveryMapController controller) {
    _mapController = controller;
    _initialCameraPositioned = false;
    _circleKeys.clear();
    controller.onPinTapped((circle) {
      final key = _circleKeys[circle];
      if (!mounted || key == null) return;
      final anchors = _selector.spatialAnchorsFromCollection(
        widget.selection.collection,
      );
      final matching = anchors.where((anchor) => anchor.candidateKey == key);
      if (matching.isEmpty) return;
      final point = matching.first;
      final keys = anchors
          .where(
            (anchor) =>
                anchor.latitude == point.latitude &&
                anchor.longitude == point.longitude,
          )
          .map((anchor) => anchor.candidateKey)
          .toSet();
      if (keys.length == 1) {
        _select(key, moveCamera: false);
      } else {
        unawaited(_chooseCoLocated(keys));
      }
    });
  }

  Future<void> _chooseCoLocated(Set<String> candidateKeys) async {
    final items = widget.selection.collection.items
        .where((item) => candidateKeys.contains(item.candidateKey))
        .toList();
    if (items.isEmpty) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheetContext) => DiscoveryCoLocatedPicker(
        items: items,
        onChoose: (item) {
          Navigator.of(sheetContext).pop();
          if (mounted) _select(item.candidateKey, moveCamera: false);
        },
      ),
    );
  }

  Future<void> _displayPins(List<DiscoverySpatialAnchor> anchors) async {
    final controller = _mapController;
    if (controller == null) return;
    final generation = ++_pinGeneration;
    final seen = <String>{};
    final selected = <DiscoverySpatialAnchor>[];
    for (final anchor in anchors) {
      final identity =
          '${anchor.latitude}:${anchor.longitude}';
      if (seen.add(identity)) selected.add(anchor);
    }
    try {
      await controller.clearPins();
      if (!mounted ||
          _mapController != controller ||
          generation != _pinGeneration)
        return;
      final pins = await controller.addPins([
        for (final anchor in selected)
          DiscoveryMapPin(anchor.latitude, anchor.longitude),
      ]);
      if (!mounted ||
          _mapController != controller ||
          generation != _pinGeneration)
        return;
      _circleKeys.clear();
      for (var i = 0; i < pins.length && i < selected.length; i++) {
        _circleKeys[pins[i]] = selected[i].candidateKey;
      }
      final latitude = _deviceLatitude;
      final longitude = _deviceLongitude;
      if (latitude != null && longitude != null) {
        await controller.showDevicePosition(latitude, longitude);
      }
    } on Object {
      // Map rendering failure does not erase a real Discovery list entry.
    }
  }

  Future<void> _recenterOnDevice() async {
    final location = widget.location;
    if (location == null) return;
    final result = await location.current();
    if (!mounted) return;
    final fix = result.fix;
    if (!result.available || fix == null || _mapController == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Position indisponible')),
      );
      return;
    }
    _clearSelection();
    setState(() {
      _deviceLatitude = fix.latitude;
      _deviceLongitude = fix.longitude;
    });
    try {
      // The marker is local-only and has no candidate identity or N2.
      await _displayPins(
        _selector.spatialAnchorsFromCollection(widget.selection.collection),
      );
      await _mapController!.moveTo(fix.latitude, fix.longitude);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de se recentrer')),
        );
      }
    }
  }

  Future<void> _onStyleReady(List<DiscoverySpatialAnchor> anchors) async {
    await _displayPins(anchors);
    final controller = _mapController;
    if (!mounted ||
        controller == null ||
        _initialCameraPositioned ||
        anchors.isEmpty) {
      return;
    }
    _initialCameraPositioned = true;
    try {
      final selected = anchors.where(
        (anchor) => anchor.candidateKey == _selectedCandidateKey,
      );
      if (selected.isNotEmpty) {
        await controller.moveTo(selected.first.latitude, selected.first.longitude);
      } else {
        await controller.fitPins([
          for (final anchor in anchors)
            DiscoveryMapPin(anchor.latitude, anchor.longitude),
        ]);
      }
    } on Object {
      _initialCameraPositioned = false;
    }
  }

  @override
  void initState() {
    super.initState();
    _selectedCandidateKey = widget.initialSelectedCandidateKey;
    if (_selectedCandidateKey != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_resolveSelected());
      });
    }
  }

  @override
  void didUpdateWidget(covariant DiscoverySpatialView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialSelectedCandidateKey !=
        widget.initialSelectedCandidateKey) {
      ++_detailGeneration;
      _selectedCandidateKey = widget.initialSelectedCandidateKey;
      _confirmedDetail = null;
    }
    final keys = widget.selection.collection.items
        .map((item) => item.candidateKey)
        .toSet();
    if (oldWidget.selection.collection.items !=
        widget.selection.collection.items) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          final anchors = _selector.spatialAnchorsFromCollection(
            widget.selection.collection,
          );
          if (!_initialCameraPositioned) {
            unawaited(_onStyleReady(anchors));
          } else {
            unawaited(_displayPins(anchors));
          }
          if (_selectedCandidateKey != null && _confirmedDetail == null) {
            unawaited(_resolveSelected());
          }
        }
      });
    }
    // Empty during network acquisition is not proof that the previously
    // selected candidate was revoked. Reconcile once a real field arrives.
    if (_selectedCandidateKey != null &&
        keys.isNotEmpty &&
        !keys.contains(_selectedCandidateKey)) {
      ++_detailGeneration;
      _selectedCandidateKey = null;
      _confirmedDetail = null;
      widget.onSelectionChanged?.call(null);
    }
  }

  DiscoveryItemPresentation? get _selectedItem {
    final items = widget.selection.collection.items;
    if (items.isEmpty) return null;
    final key = _selectedCandidateKey;
    if (key != null) {
      for (final item in items) {
        if (item.candidateKey == key &&
            _selector.spatialAnchorsFromCollection(widget.selection.collection)
                .any((anchor) => anchor.candidateKey == key)) return item;
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final points = _selector.spatialAnchorsFromCollection(
      widget.selection.collection,
    );
    final selected = _selectedItem;
    DiscoverySpatialAnchor? selectedPoint;
    if (selected != null) {
      for (final point in points) {
        if (point.candidateKey == selected.candidateKey) {
          selectedPoint = point;
          break;
        }
      }
    }

    final field = DiscoveryFieldView(
      selection: widget.selection,
      onOpen: widget.onOpen,
      onSave: widget.onSave,
      baseUri: widget.baseUri,
      shareApi: widget.shareApi,
      profileId: widget.profileId,
      allowOwnerActions: widget.allowOwnerActions,
      onPage: widget.onPage,
      onRetry: widget.onRetry,
      selectedCandidateKey: _selectedCandidateKey,
      onSelect: (item) => _select(item.candidateKey),
      selectionActionLabel: 'Voir sur la carte',
      fieldKey: widget.fieldKey,
    );

    if (points.isEmpty && !widget.showMapOnCompact) {
      return field;
    }
    final anchor = selectedPoint ?? (points.isEmpty ? null : points.first);
    final spatial = MakoloSpatialFrame(
      spatial: Stack(
        key: const Key('discover-spatial-stack'),
        children: [
          Positioned.fill(
            child: ConfiguredMakoloMapView(
              key: ValueKey(
                'discover-map-${widget.fieldKey ?? (widget.showMapOnCompact ? 'spatial' : (anchor?.candidateKey ?? 'spatial'))}',
              ),
              onMapCreated: (controller) =>
                  _mapCreated(DiscoveryMapController(controller)),
              onStyleReady: () => unawaited(_onStyleReady(points)),
              config: widget.mapConfig,
              initialViewport: MapViewport(
                center: anchor == null
                    ? const MapCoordinate(0, 0)
                    : MapCoordinate(anchor.latitude, anchor.longitude),
                zoom: anchor == null ? 1 : 11,
              ),
              fallbackBuilder: (context, state, retry) {
                final retryable = state == MakoloMapRuntimeState.error;
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(MakoloSpacing.inner),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.map_outlined),
                        const SizedBox(height: MakoloSpacing.sm),
                        const Text(
                          'Impossible d’afficher la carte.',
                          textAlign: TextAlign.center,
                        ),
                        if (retryable) ...[
                          const SizedBox(height: MakoloSpacing.md),
                          OutlinedButton(
                            onPressed: retry,
                            child: const Text('Réessayer'),
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
      compactFallback: widget.showMapOnCompact ? null : field,
      minSpatialWidth: widget.showMapOnCompact ? 0 : MakoloLayout.mapMinWidth,
    );

    if (widget.showMapOnCompact) {
      return Stack(
              key: const Key('discover-compact-map'),
              fit: StackFit.expand,
              children: [
                spatial,
                if (points.isEmpty &&
                    widget.selection.hasSnapshot &&
                    widget.selection.surface.availability == MakoloAvailabilityCue.empty)
                  Positioned(
                    top: 72,
                    left: MakoloSpacing.sm,
                    right: MakoloSpacing.sm,
                    child: Center(
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(MakoloSpacing.sm),
                          child: Text(
                            'Aucune possibilité localisée',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                        ),
                      ),
                    ),
                  ),
                if (widget.location != null && widget.mapConfig.enabled)
                  Positioned(
                    top: 104,
                    right: MakoloSpacing.sm,
                    child: Material(
                      elevation: 2,
                      borderRadius: BorderRadius.circular(24),
                      color: Theme.of(context).colorScheme.surface,
                      child: IconButton(
                        tooltip: 'Ma position',
                        onPressed: () => unawaited(_recenterOnDevice()),
                        icon: const Icon(Icons.my_location_rounded),
                      ),
                    ),
                  ),
                if (selected != null)
                  Positioned(
                    left: MakoloSpacing.sm,
                    right: MakoloSpacing.sm,
                    bottom: MakoloSpacing.sm,
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        maxHeight: MediaQuery.sizeOf(context).height * 0.4,
                      ),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(MakoloSpacing.md),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      selected.title,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(context).textTheme.titleMedium,
                                    ),
                                  ),
                                  IconButton(
                                    tooltip: 'Fermer l’aperçu',
                                    onPressed: () {
                                      setState(() => _selectedCandidateKey = null);
                                      widget.onSelectionChanged?.call(null);
                                    },
                                    icon: const Icon(Icons.close),
                                  ),
                                ],
                              ),
                              if (selected.place != null)
                                Text(selected.place!, maxLines: 1, overflow: TextOverflow.ellipsis),
                              Align(
                                alignment: Alignment.centerRight,
                                child: TextButton(
                                  onPressed: () => widget.onOpen(selected),
                                  child: const Text('Voir le détail'),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            );
    }

    return MakoloAdaptiveSplit(
      splitAt: MakoloLayout.discoverSpatialMinWidth,
      field: field,
      focus: SizedBox(
        key: const Key('discover-spatial-pane'),
        height: 620,
        child: spatial,
      ),
      narrow: field,
      focusMin: MakoloLayout.mapMinWidth,
      focusPreferred: 560,
      focusMax: 720,
    );
  }
}

class _DiscoveryScrollableField extends StatelessWidget {
  const _DiscoveryScrollableField({
    required this.selection,
    required this.onOpen,
    this.onSave,
    this.baseUri,
    this.shareApi,
    this.profileId,
    this.allowOwnerActions = true,
    this.onPage,
    this.autoLoadMore = false,
    this.loadingMore = false,
    this.loadMoreFailed = false,
    this.selectedCandidateKey,
    this.onSelect,
    this.selectionActionLabel,
    this.selectOnCardTap = false,
    this.onMap,
    this.onWatch,
    this.fieldKey,
    this.scrollController,
  });

  final DiscoveryFieldSelection selection;
  final DiscoveryOpenItem onOpen;
  final DiscoverySaveItem? onSave;
  final Uri? baseUri;
  final MakoloApiClient? shareApi;
  final String? profileId;
  final bool allowOwnerActions;
  final ValueChanged<int>? onPage;
  final bool autoLoadMore;
  final bool loadingMore;
  final bool loadMoreFailed;
  final String? selectedCandidateKey;
  final ValueChanged<DiscoveryItemPresentation>? onSelect;
  final String? selectionActionLabel;
  final bool selectOnCardTap;
  final VoidCallback? onMap;
  final VoidCallback? onWatch;
  final String? fieldKey;
  final ScrollController? scrollController;

  @override
  Widget build(BuildContext context) {
    final items = selection.collection.items;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.hasBoundedWidth
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        final widthClass = MakoloLayout.widthClassFor(width);
        final wide =
            widthClass == MakoloWidthClass.wide ||
            widthClass == MakoloWidthClass.veryWide;

        final units = [
          for (final item in items)
            _DiscoveryUnit(
              key: ValueKey('discover-unit-${item.candidateKey}'),
              item: item,
              selected: selectedCandidateKey == item.candidateKey,
              baseUri: baseUri,
              shareApi: shareApi,
              profileId: profileId,
              allowOwnerActions: allowOwnerActions,
              onSave: onSave == null ? null : () => onSave!(item),
              onTap: () {
                if (selectOnCardTap && onSelect != null) {
                  onSelect!(item);
                } else {
                  onOpen(item);
                }
              },
              onSelect:
                  selectionActionLabel == null ||
                      onSelect == null ||
                      !item.isMappable
                  ? null
                  : () => onSelect!(item),
              selectionActionLabel: selectionActionLabel,
            ),
        ];

        final list = ListView(
          controller: scrollController,
          key: PageStorageKey<String>(
            fieldKey == null
                ? (autoLoadMore
                      ? 'discover-continuous-field'
                      : 'discover-page-${selection.collection.page}')
                : (autoLoadMore
                      ? 'discover-$fieldKey-continuous'
                      : 'discover-$fieldKey-${selection.collection.page}'),
          ),
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.only(
            top: MakoloSpacing.sm,
            bottom: MakoloSpacing.xl,
          ),
          children: [
            MakoloContentFrame(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Opportunités à découvrir',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: MakoloSpacing.lg),
                ],
              ),
            ),
            if (wide)
              MakoloContentFrame(
                child: MakoloAdaptiveGrid(
                  key: const Key('discover-wide-grid'),
                  minUnitWidth: MakoloLayout.unitMinWidth,
                  maxColumns: 3,
                  children: units,
                ),
              )
            else
              Column(
                key: const Key('discover-compact-field'),
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (var index = 0; index < units.length; index++) ...[
                    units[index],
                    if (index < units.length - 1)
                      const SizedBox(height: MakoloSpacing.sm),
                  ],
                ],
              ),
            MakoloContentFrame(
              child: Column(
                children: [
                  if (autoLoadMore && loadingMore) ...[
                    const SizedBox(height: MakoloSpacing.lg),
                    const Center(child: CircularProgressIndicator()),
                  ],
                  if (autoLoadMore && loadMoreFailed) ...[
                    const SizedBox(height: MakoloSpacing.md),
                    TextButton(
                      onPressed: onPage == null
                          ? null
                          : () => onPage!(selection.collection.page + 1),
                      child: const Text('Réessayer le chargement'),
                    ),
                  ],
                  if (!loadingMore &&
                      !loadMoreFailed &&
                      selection.states.contains(
                        DiscoveryFieldState.endOfField,
                      )) ...[
                    const SizedBox(height: MakoloSpacing.lg),
                    const _DiscoveryEndOfField(),
                  ],
                  if (!autoLoadMore &&
                      (selection.collection.page > 1 ||
                          selection.collection.hasNext)) ...[
                    const SizedBox(height: MakoloSpacing.lg),
                    _DiscoveryPagination(
                      collection: selection.collection,
                      onPage: onPage,
                    ),
                  ],
                ],
              ),
            ),
          ],
        );
        if (!autoLoadMore || onPage == null) return list;
        return LoadMoreOnScroll(
          hasMore: selection.collection.hasNext && !loadMoreFailed,
          loading: loadingMore,
          loadMore: () => onPage!(selection.collection.page + 1),
          child: list,
        );
      },
    );
  }
}

class _DiscoveryUnit extends StatelessWidget {
  const _DiscoveryUnit({
    super.key,
    required this.item,
    required this.selected,
    required this.onTap,
    this.onSave,
    this.baseUri,
    this.shareApi,
    this.profileId,
    this.allowOwnerActions = true,
    this.onSelect,
    this.selectionActionLabel,
  });

  final DiscoveryItemPresentation item;
  final bool selected;
  final VoidCallback onTap;
  final Future<void> Function()? onSave;
  final Uri? baseUri;
  final MakoloApiClient? shareApi;
  final String? profileId;
  final bool allowOwnerActions;
  final VoidCallback? onSelect;
  final String? selectionActionLabel;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: selected
          ? BoxDecoration(
              border: Border.all(
                color: Theme.of(context).colorScheme.primary,
                width: 2,
              ),
              borderRadius: BorderRadius.circular(MakoloRadii.card),
            )
          : const BoxDecoration(),
      child: DiscoveryPossibilityUnit(
        item: item,
        onOpen: onTap,
        onSave: onSave,
        baseUri: baseUri,
        shareApi: shareApi,
        profileId: profileId,
        allowOwnerActions: allowOwnerActions,
        shareAuthenticated: shareApi != null,
        onSelect: onSelect,
        selectionActionLabel: selectionActionLabel,
      ),
    );
  }
}

class _DiscoveryMedia extends StatelessWidget {
  const _DiscoveryMedia({required this.item, this.baseUri});

  final DiscoveryItemPresentation item;
  final Uri? baseUri;

  @override
  Widget build(BuildContext context) {
    final uri = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    final resolved = uri == null
        ? null
        : (uri.hasScheme ? uri : baseUri?.resolveUri(uri));
    Widget? child;
    if (resolved != null &&
        (resolved.scheme == 'https' || resolved.scheme == 'http')) {
      // Only public first-party images are retained automatically. An
      // external URL keeps its existing non-persistent presentation.
      final mediaBaseUri = baseUri;
      child =
          mediaBaseUri != null &&
              resolved.origin == mediaBaseUri.origin &&
              DiscoveryOfflineStore.isPublishedRecognitionUri(
                resolved,
                trustedOrigin: mediaBaseUri,
              )
          ? RetainedPublicDiscoveryImage(
              url: resolved,
              trustedOrigin: mediaBaseUri,
              placeholder: MakoloMediaPlaceholder(
                label: item.eyebrow ?? 'Média indisponible',
              ),
            )
          : Image.network(
              resolved.toString(),
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => MakoloMediaPlaceholder(
                label: item.eyebrow ?? 'Média indisponible',
              ),
            );
    } else if (item.routeLabel != null) {
      child = ColoredBox(
        color: context.makoloSurfaces.low,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(MakoloSpacing.lg),
            child: Text(
              item.routeLabel!,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
        ),
      );
    }

    return MakoloMediaFrame(
      aspect: MakoloMediaAspect.landscape,
      semanticLabel: item.imageUrl == null ? null : 'Média de ${item.title}',
      placeholder: MakoloMediaPlaceholder(label: item.eyebrow ?? 'Possibilité'),
      child: child,
    );
  }
}

class _DiscoveryFocusPane extends StatelessWidget {
  const _DiscoveryFocusPane({
    required this.item,
    required this.onClose,
    required this.onOpen,
    this.baseUri,
  });

  final DiscoveryItemPresentation item;
  final Uri? baseUri;
  final VoidCallback onClose;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      key: const Key('discover-focus-depth'),
      padding: const EdgeInsets.all(MakoloSpacing.inner),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextButton.icon(
            onPressed: onClose,
            icon: const Icon(Icons.arrow_back_rounded),
            label: const Text('Découvrir'),
          ),
          const SizedBox(height: MakoloSpacing.md),
          if (item.imageUrl != null || item.routeLabel != null) ...[
            _DiscoveryMedia(item: item, baseUri: baseUri),
            const SizedBox(height: MakoloSpacing.lg),
          ],
          if (item.eyebrow != null)
            Text(
              item.eyebrow!,
              style: Theme.of(context).textTheme.labelLarge
                  ?.copyWith(color: Theme.of(context).colorScheme.primary),
            ),
          const SizedBox(height: MakoloSpacing.xs),
          Text(item.title, style: Theme.of(context).textTheme.headlineSmall),
          if (item.summary.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(item.summary),
          ],
          if (item.owner != null ||
              item.place != null ||
              item.timing != null ||
              item.price != null ||
              item.distanceKm != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            MakoloMetadata(
              items: [
                if (item.owner != null)
                  MakoloMetadataItem(
                    item.owner!,
                    icon: Icons.business_outlined,
                  ),
                if (item.place != null)
                  MakoloMetadataItem(item.place!, icon: Icons.place_outlined),
                if (item.distanceKm != null)
                  MakoloMetadataItem(
                    '${item.distanceKm! < 10 ? item.distanceKm!.toStringAsFixed(1) : item.distanceKm!.round()} km',
                    icon: Icons.near_me_outlined,
                  ),
                if (item.timing != null)
                  MakoloMetadataItem(
                    item.timing!,
                    icon: Icons.schedule_outlined,
                  ),
                if (item.price != null)
                  MakoloMetadataItem(
                    item.price!,
                    icon: Icons.payments_outlined,
                  ),
              ],
            ),
          ],
          if (item.availability != null ||
              item.canSave ||
              item.canUnsave ||
              item.savedState == 'saved') ...[
            const SizedBox(height: MakoloSpacing.md),
            Row(
              children: [
                if (item.availability != null)
                  MakoloStatus(label: item.availability!),
                const Spacer(),
                if (item.canSave ||
                    item.canUnsave ||
                    item.savedState == 'saved')
                  DiscoveryOrbitIcon(
                    saved: item.savedState == 'saved',
                    color: item.savedState == 'saved'
                        ? Theme.of(context).colorScheme.primary
                        : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
              ],
            ),
          ],
          const SizedBox(height: MakoloSpacing.lg),
          FilledButton.icon(
            onPressed: onOpen,
            icon: const Icon(Icons.arrow_forward_rounded),
            label: const Text('Ouvrir le détail'),
          ),
        ],
      ),
    );
  }
}

class _DiscoveryEmptyState extends StatelessWidget {
  const _DiscoveryEmptyState({
    required this.states,
    this.onRetry,
    this.onResetCriteria,
  });

  final Set<DiscoveryFieldState> states;
  final VoidCallback? onRetry;
  final VoidCallback? onResetCriteria;

  @override
  Widget build(BuildContext context) {
    if (states.contains(DiscoveryFieldState.contractError)) {
      return _EmptyBody(
        icon: Icons.error_outline_rounded,
        title: 'Informations indisponibles.',
        actionLabel: onRetry == null ? null : 'Réessayer',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.continuationRejected)) {
      return _EmptyBody(
        icon: Icons.refresh_rounded,
        title: 'Recherche à actualiser.',
        actionLabel: onRetry == null ? null : 'Actualiser la recherche',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.serverUnavailableNoSnapshot)) {
      return _EmptyBody(
        icon: Icons.cloud_off_outlined,
        title: 'Service momentanément indisponible.',
        actionLabel: onRetry == null ? null : 'Réessayer',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.offlineNoSnapshot) ||
        states.contains(DiscoveryFieldState.offlineWithSnapshot)) {
      return _EmptyBody(
        icon: Icons.info_outline_rounded,
        title: 'Connexion indisponible.',
        actionLabel: onRetry == null ? null : 'Réessayer',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.noMatch)) {
      return _EmptyBody(
        icon: Icons.search_off_outlined,
        title: 'Aucun résultat.',
        actionLabel: onResetCriteria == null ? null : 'Modifier les filtres',
        onAction: onResetCriteria,
      );
    }
    return const _EmptyBody(
      icon: Icons.explore_outlined,
      title: 'Aucune possibilité pour le moment.',
    );
  }
}

class _EmptyBody extends StatelessWidget {
  const _EmptyBody({
    required this.icon,
    required this.title,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(MakoloSpacing.inner),
      children: [
        const SizedBox(height: 72),
        Icon(icon, size: 32),
        const SizedBox(height: MakoloSpacing.md),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (actionLabel != null && onAction != null) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Center(
            child: OutlinedButton(
              onPressed: onAction,
              child: Text(actionLabel!),
            ),
          ),
        ],
      ],
    );
  }
}

class _DiscoveryEndOfField extends StatelessWidget {
  const _DiscoveryEndOfField();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Fin du champ actuel',
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: context.makoloSurfaces.low,
          borderRadius: BorderRadius.circular(MakoloRadii.card),
        ),
        child: const Padding(
          padding: EdgeInsets.all(MakoloSpacing.md),
          child: Text('Vous avez tout exploré.', textAlign: TextAlign.center),
        ),
      ),
    );
  }
}

class _DiscoveryPagination extends StatelessWidget {
  const _DiscoveryPagination({required this.collection, required this.onPage});

  final DiscoveryCollectionPresentation collection;
  final ValueChanged<int>? onPage;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        OutlinedButton.icon(
          onPressed: collection.page > 1 && onPage != null
              ? () => onPage!(collection.page - 1)
              : null,
          icon: const Icon(Icons.chevron_left_rounded),
          label: const Text('Précédent'),
        ),
        const Spacer(),
        Text(
          'Page ${collection.page}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const Spacer(),
        FilledButton.icon(
          onPressed: collection.hasNext && onPage != null
              ? () => onPage!(collection.page + 1)
              : null,
          icon: const Icon(Icons.chevron_right_rounded),
          label: const Text('Suivant'),
        ),
      ],
    );
  }
}
