import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/presentation_media.dart';
import '../../design/surface_states.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/location/location_service.dart';
import '../../platform/permissions/permission_gateway.dart';
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
    this.collectiveReadOnly = false,
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
  final bool collectiveReadOnly;
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
      initialLoading: const MakoloCardSkeleton(
        kind: MakoloCardSkeletonKind.discover,
      ),
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
      content: DiscoveryFollowScope(
        key: ValueKey<String?>(profileId),
        profileId: profileId,
        child: _DiscoveryScrollableField(
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
    this.baseUri,
  });

  final List<DiscoveryItemPresentation> items;
  final ValueChanged<DiscoveryItemPresentation> onChoose;
  final Uri? baseUri;

  @override
  State<DiscoveryCoLocatedPicker> createState() =>
      _DiscoveryCoLocatedPickerState();
}

class _DiscoveryCoLocatedPickerState extends State<DiscoveryCoLocatedPicker> {
  @override
  Widget build(BuildContext context) {
    final items = widget.items;
    final place = items.isEmpty ? null : items.first.place;
    final commonPlace =
        place != null &&
        place.trim().isNotEmpty &&
        items.every((item) => item.place == place);
    final screenHeight = MediaQuery.sizeOf(context).height;
    // Four initial rows on a regular phone. Scrolling first expands the
    // sheet, then naturally reveals all remaining admitted opportunities.
    final initialRows = math.min(items.length, 4);
    final requiredHeight = 100.0 + initialRows * 105.0;
    final initialSize = (requiredHeight / screenHeight)
        .clamp(0.26, 0.80)
        .toDouble();
    return DraggableScrollableSheet(
      key: const Key('discover-map-colocated-sheet'),
      expand: false,
      initialChildSize: initialSize,
      minChildSize: 0.26,
      maxChildSize: 0.92,
      builder: (context, scrollController) => ListView.builder(
        controller: scrollController,
        padding: const EdgeInsets.fromLTRB(
          MakoloSpacing.md,
          MakoloSpacing.sm,
          MakoloSpacing.md,
          MakoloSpacing.xl,
        ),
        itemCount: items.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.place_rounded,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: MakoloSpacing.xs),
                      Expanded(
                        child: Text(
                          '${items.length} opportunités ici',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                    ],
                  ),
                  if (commonPlace)
                    Padding(
                      padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                      child: Text(
                        place,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                ],
              ),
            );
          }
          final item = items[index - 1];
          return Padding(
            padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
            child: Card(
              margin: EdgeInsets.zero,
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                key: ValueKey('discover-map-place-choice-${item.candidateKey}'),
                onTap: () => widget.onChoose(item),
                child: Padding(
                  padding: const EdgeInsets.all(MakoloSpacing.sm),
                  child: Row(
                    children: [
                      _DiscoveryMapThumbnail(
                        item: item,
                        baseUri: widget.baseUri,
                      ),
                      const SizedBox(width: MakoloSpacing.sm),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.title,
                              maxLines:
                                  item.owner == null && item.timing == null
                                  ? 3
                                  : 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                            if (item.owner != null || item.eyebrow != null)
                              Text(
                                item.owner ?? item.eyebrow!,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            if (item.timing != null)
                              Row(
                                children: [
                                  const Icon(Icons.schedule_outlined, size: 14),
                                  const SizedBox(width: 4),
                                  Expanded(
                                    child: Text(
                                      item.timing!,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall,
                                    ),
                                  ),
                                ],
                              ),
                            if (item.place != null && !commonPlace)
                              Text(
                                item.place!,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right_rounded),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Visual recognition uses only a real image already published by the owner.
/// A neutral icon replaces the thumbnail when no valid media is available.
class _DiscoveryMapThumbnail extends StatelessWidget {
  const _DiscoveryMapThumbnail({
    required this.item,
    this.baseUri,
    this.size = 52,
  });

  final DiscoveryItemPresentation item;
  final Uri? baseUri;
  final double size;

  @override
  Widget build(BuildContext context) {
    // Prefer the opportunity's published media. The publisher avatar is a
    // valid fallback only when it is already in the admitted presentation.
    final owner = item.wire['owner'];
    final representation = owner is Map ? owner['representation'] : null;
    final avatar =
        representation is Map && representation['avatar_url'] is String
        ? representation['avatar_url'] as String
        : null;
    final mediaUrl = item.imageUrl ?? avatar;
    final uri = mediaUrl == null ? null : Uri.tryParse(mediaUrl);
    final resolved = uri == null
        ? null
        : uri.hasScheme
        ? uri
        : baseUri?.resolveUri(uri);
    final placeholder = ColoredBox(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Center(
        child: Icon(switch (item.representationKind ?? item.family) {
          'event' => Icons.event_available_outlined,
          'transport' || 'route' => Icons.directions_bus_outlined,
          'service' || 'service_activity' => Icons.handshake_outlined,
          'funding' || 'funding_activity' => Icons.account_balance_outlined,
          'opportunity' => Icons.school_outlined,
          _ => Icons.explore_outlined,
        }, color: Theme.of(context).colorScheme.onPrimaryContainer),
      ),
    );
    Widget content = placeholder;
    if (resolved != null &&
        (resolved.scheme == 'https' || resolved.scheme == 'http')) {
      final trusted =
          baseUri != null &&
          resolved.origin == baseUri!.origin &&
          DiscoveryOfflineStore.isPublishedRecognitionUri(
            resolved,
            trustedOrigin: baseUri!,
          );
      content = trusted
          ? RetainedPublicDiscoveryImage(
              url: resolved,
              trustedOrigin: baseUri!,
              placeholder: placeholder,
            )
          : Image.network(
              resolved.toString(),
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => placeholder,
            );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: SizedBox(width: size, height: size, child: content),
    );
  }
}

class _DiscoveryMapFact extends StatelessWidget {
  const _DiscoveryMapFact({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: MakoloSpacing.xs),
      child: Row(
        children: [
          Icon(icon, size: 16, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: MakoloSpacing.xs),
          Expanded(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

/// Short-lived context for a map selection. Never a second Discovery N2.
class _DiscoveryMapPreview extends StatelessWidget {
  const _DiscoveryMapPreview({
    required this.item,
    required this.place,
    required this.detail,
    required this.saving,
    required this.onClose,
    required this.onOpen,
    required this.onSave,
    this.onDirections,
    this.shareApi,
    this.shareAuthenticated = false,
    this.collectiveReadOnly = false,
    this.baseUri,
  });

  final DiscoveryItemPresentation item;
  final String? place;
  final DiscoveryItemPresentation? detail;
  final bool saving;
  final VoidCallback onClose;
  final VoidCallback onOpen;
  final VoidCallback? onSave;
  final VoidCallback? onDirections;
  final MakoloApiClient? shareApi;
  final bool shareAuthenticated;
  final bool collectiveReadOnly;
  final Uri? baseUri;

  @override
  Widget build(BuildContext context) {
    final resolved = detail;
    final canChangeSaved =
        onSave != null &&
        resolved != null &&
        (resolved.savedState == 'saved'
            ? resolved.canUnsave
            : resolved.canSave);
    // Carte may know a pin before its owner's N2 has been verified.
    // Keep the three Découvrir actions visible, but never turn a map
    // coordinate into Save/Sharing authority.
    final saved = resolved?.savedState == 'saved';
    return Card(
      key: const Key('discover-map-selected-preview'),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _DiscoveryMapThumbnail(
                  item: resolved ?? item,
                  baseUri: baseUri,
                  size: 68,
                ),
                const SizedBox(width: MakoloSpacing.sm),
                Expanded(
                  child: Text(
                    item.title,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                MakoloIconActionButton(
                  tooltip: 'Fermer l’aperçu',
                  onPressed: onClose,
                  icon: Icons.close_rounded,
                ),
              ],
            ),
            if ((resolved?.eyebrow ?? item.eyebrow)?.trim().isNotEmpty == true)
              Text(
                (resolved?.eyebrow ?? item.eyebrow)!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelMedium,
              ),
            if (place != null && place!.trim().isNotEmpty)
              _DiscoveryMapFact(icon: Icons.place_outlined, label: place!),
            if ((resolved?.owner ?? item.owner) != null)
              _DiscoveryMapFact(
                icon: Icons.business_outlined,
                label: (resolved?.owner ?? item.owner)!,
              ),
            if ((resolved?.timing ?? item.timing) != null)
              _DiscoveryMapFact(
                icon: Icons.schedule_outlined,
                label: (resolved?.timing ?? item.timing)!,
              ),
            if ((resolved?.summary.isNotEmpty ?? false) ||
                item.summary.trim().isNotEmpty)
              Padding(
                key: const Key('discover-map-summary'),
                padding: const EdgeInsets.only(top: MakoloSpacing.sm),
                child: Text(
                  resolved?.summary.trim().isNotEmpty == true
                      ? resolved!.summary
                      : item.summary,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            if (onDirections != null)
              Align(
                alignment: Alignment.centerLeft,
                child: MakoloActionButton(
                  key: const Key('discover-map-directions'),
                  label: 'Itinéraire',
                  onPressed: onDirections,
                  icon: Icons.directions_outlined,
                  appearance: MakoloActionAppearance.quiet,
                ),
              ),
            const SizedBox(height: MakoloSpacing.xs),
            const Divider(height: 1),
            Row(
              children: [
                if (!collectiveReadOnly)
                  Expanded(
                    child: IconButton(
                      key: const Key('discover-map-save'),
                      tooltip: saving
                          ? 'Enregistrement…'
                          : saved
                          ? 'Retirer des enregistrements'
                          : 'Enregistrer',
                      onPressed: canChangeSaved && !saving ? onSave : null,
                      icon: DiscoveryOrbitIcon(
                        saved: saved,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ),
                Expanded(
                  child: MakoloIconActionButton(
                    key: const Key('discover-map-open-n2'),
                    tooltip: 'Voir l’opportunité',
                    onPressed: onOpen,
                    icon: Icons.arrow_forward_rounded,
                  ),
                ),
                if (!collectiveReadOnly)
                  Expanded(
                    child: Center(
                      child: DiscoveryShareControl(
                        key: ValueKey(
                          'discover-map-share-${(resolved ?? item).candidateKey}',
                        ),
                        item: resolved ?? item,
                        api: shareApi,
                        authenticated: shareAuthenticated,
                        // Same owner Sharing operation as N1, in a map-safe sheet.
                        enabled: resolved != null && !saving,
                        showAsSheet: true,
                        baseUri: baseUri,
                        iconOnly: true,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
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
    this.initialMapFocus,
    this.onSave,
    this.onDirections,
    this.resolveItem,
    this.baseUri,
    this.shareApi,
    this.shareAuthenticated = false,
    this.profileId,
    this.allowOwnerActions = true,
    this.collectiveReadOnly = false,
    this.onPage,
    this.autoLoadMore = false,
    this.loadingMore = false,
    this.loadMoreFailed = false,
    this.onRetry,
    this.initialSelectedCandidateKey,
    this.showMapOnCompact = false,
    this.fieldKey,
    this.onSelectionChanged,
    this.onFocusedAnchorChanged,
    this.initialFocusedAnchor,
    this.detailRefreshRevision = 0,
    this.spatialRevision,
    this.restoredViewport,
    this.onViewportChanged,
  });

  final DiscoveryFieldSelection selection;
  final MakoloMapsConfig mapConfig;
  final DiscoveryOpenItem onOpen;
  final LocationCapability? location;

  /// Search-center only; not the user's GPS or a canonical Makolo Place.
  final MapCoordinate? initialMapFocus;
  final DiscoverySaveItem? onSave;

  /// Only the selected public spatial fact is passed to navigation.
  final ValueChanged<DiscoverySpatialAnchor>? onDirections;
  final DiscoveryResolveItem? resolveItem;
  final Uri? baseUri;
  final MakoloApiClient? shareApi;
  final bool shareAuthenticated;
  final String? profileId;
  final bool allowOwnerActions;
  final bool collectiveReadOnly;
  final ValueChanged<int>? onPage;
  final bool autoLoadMore;
  final bool loadingMore;
  final bool loadMoreFailed;
  final VoidCallback? onRetry;
  final String? initialSelectedCandidateKey;
  final bool showMapOnCompact;
  final String? fieldKey;
  final ValueChanged<String?>? onSelectionChanged;
  final ValueChanged<DiscoverySpatialAnchor?>? onFocusedAnchorChanged;
  final DiscoverySpatialAnchor? initialFocusedAnchor;

  /// N2 returned; refresh owner-confirmed actions, never the map's camera.
  final int detailRefreshRevision;

  /// Stable owner snapshot revision, independent from widget rebuilds.
  final DateTime? spatialRevision;
  final MapViewport? restoredViewport;
  final ValueChanged<MapViewport>? onViewportChanged;

  @override
  State<DiscoverySpatialView> createState() => _DiscoverySpatialViewState();
}

class _DiscoverySpatialViewState extends State<DiscoverySpatialView>
    with WidgetsBindingObserver {
  static const _selector = DiscoverySelector();
  String? _selectedCandidateKey;
  DiscoveryMapController? _mapController;
  final Map<Object, DiscoverySpatialAnchor> _circleAnchors = {};
  final Map<String, DiscoverySpatialAnchor> _locationAnchors = {};
  DiscoverySpatialAnchor? _focusedAnchor;
  int _pinGeneration = 0;
  Future<void> _pinRender = Future<void>.value();
  bool _initialCameraPositioned = false;
  double? _deviceLatitude;
  double? _deviceLongitude;
  LocationWatchHandle? _deviceWatch;
  bool _deviceWatchStarting = false;
  bool _trackingRequested = false;
  bool _locationBusy = false;
  int _trackingGeneration = 0;
  Future<void> _deviceRender = Future<void>.value();
  DiscoveryItemPresentation? _confirmedDetail;
  int _detailGeneration = 0;
  bool _savingSelected = false;

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopDeviceWatch();
    ++_pinGeneration;
    ++_detailGeneration;
    _circleAnchors.clear();
    _locationAnchors.clear();
    _mapController = null;
    super.dispose();
  }

  void _select(
    String key, {
    bool moveCamera = true,
    DiscoverySpatialAnchor? anchor,
  }) {
    final changed = _selectedCandidateKey != key;
    setState(() {
      _selectedCandidateKey = key;
      _focusedAnchor = anchor;
      if (changed) _confirmedDetail = null;
    });
    widget.onSelectionChanged?.call(key);
    widget.onFocusedAnchorChanged?.call(anchor);
    if (changed) unawaited(_resolveSelected());
    unawaited(
      _displayPins(
        _selector.spatialAnchorsFromCollection(widget.selection.collection),
      ),
    );
    if (!moveCamera) return;
    final anchors = _selector.spatialAnchorsFromCollection(
      widget.selection.collection,
    );
    for (final point in anchors) {
      if (point.candidateKey != key) continue;
      final target = anchor ?? point;
      final controller = _mapController;
      if (controller != null) {
        unawaited(_moveCamera(controller, target));
      }
      break;
    }
  }

  void _clearSelection() {
    ++_detailGeneration;
    setState(() {
      _selectedCandidateKey = null;
      _focusedAnchor = null;
      _confirmedDetail = null;
    });
    widget.onSelectionChanged?.call(null);
    widget.onFocusedAnchorChanged?.call(null);
    unawaited(
      _displayPins(
        _selector.spatialAnchorsFromCollection(widget.selection.collection),
      ),
    );
  }

  Future<void> _resolveSelected() async {
    final resolver = widget.resolveItem;
    final key = _selectedCandidateKey;
    if (resolver == null || key == null) return;
    final candidates = widget.selection.collection.items.where(
      (item) => item.candidateKey == key,
    );
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
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              item.savedState == 'saved'
                  ? 'Retiré des enregistrements.'
                  : 'Opportunité enregistrée.',
            ),
          ),
        );
        // This is a new owner-confirmed saved state, not an optimistic one.
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
      await controller.focusLocation(anchor.latitude, anchor.longitude);
    } on Object {
      // The list selection remains usable while the map is unavailable.
    }
  }

  void _mapCreated(DiscoveryMapController controller) {
    _mapController = controller;
    _initialCameraPositioned = widget.restoredViewport != null;
    _circleAnchors.clear();
    _locationAnchors.clear();
    // Annotation tap is retained only for older styles that cannot install
    // the native clustered source. Both paths resolve the same candidates.
    controller.onPinTapped((circle) {
      final point = _circleAnchors[circle];
      if (mounted && point != null) _openMapPoint(point);
    });
  }

  void _openMapPoint(DiscoverySpatialAnchor point) {
    final anchors = _selector.spatialAnchorsFromCollection(
      widget.selection.collection,
    );
    final matches = anchors
        .where(
          (anchor) =>
              anchor.latitude == point.latitude &&
              anchor.longitude == point.longitude,
        )
        .toList();
    final keys = matches.map((anchor) => anchor.candidateKey).toSet();
    if (keys.isEmpty) return;
    if (keys.length == 1) {
      _select(keys.first, anchor: matches.first);
    } else {
      unawaited(_chooseCoLocated(keys, at: point));
    }
  }

  Future<void> _onMapFeatureTap(math.Point<double> screenPoint) async {
    final controller = _mapController;
    if (controller == null) return;
    final locationKey = await controller.selectRenderedPoint(screenPoint);
    if (!mounted || _mapController != controller || locationKey == null) {
      // Cluster taps zoom to the native expansion level in the controller.
      return;
    }
    final anchor = _locationAnchors[locationKey];
    if (anchor != null) _openMapPoint(anchor);
  }

  Future<void> _chooseCoLocated(
    Set<String> candidateKeys, {
    required DiscoverySpatialAnchor at,
  }) async {
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
        baseUri: widget.baseUri,
        onChoose: (item) {
          Navigator.of(sheetContext).pop();
          if (!mounted) return;
          final matches = _selector
              .spatialAnchorsFromCollection(widget.selection.collection)
              .where(
                (anchor) =>
                    anchor.candidateKey == item.candidateKey &&
                    anchor.latitude == at.latitude &&
                    anchor.longitude == at.longitude,
              );
          _select(
            item.candidateKey,
            anchor: matches.isEmpty ? null : matches.first,
            moveCamera: true,
          );
        },
      ),
    );
  }

  Future<void> _displayPins(List<DiscoverySpatialAnchor> anchors) {
    final controller = _mapController;
    if (controller == null) return Future<void>.value();
    final generation = ++_pinGeneration;
    final locations = <String, DiscoverySpatialAnchor>{};
    final candidatesAtLocation = <String, Set<String>>{};
    final itemByCandidate = {
      for (final item in widget.selection.collection.items)
        item.candidateKey: item,
    };
    final selectedCandidate = _selectedCandidateKey;
    final focused = _focusedAnchor;
    String? selectedLocation;
    for (final anchor in anchors) {
      final key = '${anchor.latitude}:${anchor.longitude}';
      locations.putIfAbsent(key, () => anchor);
      candidatesAtLocation
          .putIfAbsent(key, () => <String>{})
          .add(anchor.candidateKey);
      if (anchor.candidateKey == selectedCandidate &&
          (selectedLocation == null ||
              (focused?.candidateKey == selectedCandidate &&
                  focused?.latitude == anchor.latitude &&
                  focused?.longitude == anchor.longitude))) {
        selectedLocation = key;
      }
    }
    // MapLibre source updates are asynchronous. Serialize them to prevent a
    // stale field revision or style callback from overwriting newer points.
    final operation = _pinRender.then((_) async {
      if (!mounted ||
          _mapController != controller ||
          generation != _pinGeneration) {
        return;
      }
      try {
        final pins = await controller.renderPins([
          for (final entry in locations.entries)
            DiscoveryMapPin(
              entry.value.latitude,
              entry.value.longitude,
              locationKey: entry.key,
              opportunityCount: candidatesAtLocation[entry.key]!.length,
              selected: selectedLocation == entry.key,
              symbol: _glyphForLocation(
                entry.value,
                candidatesAtLocation[entry.key]!.length,
                itemByCandidate,
              ),
            ),
        ]);
        if (!mounted ||
            _mapController != controller ||
            generation != _pinGeneration) {
          return;
        }
        _locationAnchors
          ..clear()
          ..addAll(locations);
        _circleAnchors.clear();
        final selected = locations.values.toList();
        for (var i = 0; i < pins.length && i < selected.length; i++) {
          _circleAnchors[pins[i]] = selected[i];
        }
        final latitude = _deviceLatitude;
        final longitude = _deviceLongitude;
        if (latitude != null && longitude != null) {
          await controller.showDevicePosition(latitude, longitude);
        }
      } on Object {
        // Renderer failure must not erase the admitted local collection.
      }
    });
    _pinRender = operation;
    return operation;
  }

  /// Only a single admitted, published vertical gets a marker pictogram.
  /// A shared coordinate retains its numeric opportunity count instead.
  static String _glyphForLocation(
    DiscoverySpatialAnchor anchor,
    int count,
    Map<String, DiscoveryItemPresentation> items,
  ) {
    if (count != 1) return '';
    final item = items[anchor.candidateKey];
    return switch (item?.representationKind ?? item?.family) {
      'event' => '★',
      'transport' || 'route' => '➜',
      'service' || 'service_activity' => '✦',
      'funding' || 'funding_activity' => '◆',
      'opportunity' => '✧',
      _ => '',
    };
  }

  void _stopDeviceWatch() {
    ++_trackingGeneration;
    final watch = _deviceWatch;
    _deviceWatch = null;
    if (watch != null) unawaited(watch.stop());
  }

  Future<void> _resumeAuthorizedLocation() async {
    final location = widget.location;
    if (location == null || !widget.mapConfig.enabled) return;
    try {
      final permission = await location.permissions.status(
        MakoloPermission.locationWhenInUse,
      );
      if (!mounted || location != widget.location) return;
      if (!permission.permitsCapability) return;
      // No request/prompt: reuse the already-authorized foreground stream.
      _trackingRequested = true;
      await _startDeviceWatch();
    } on Object {
      // A map remains usable if a device cannot report permission status.
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (_trackingRequested) {
        unawaited(_startDeviceWatch());
      } else {
        unawaited(_resumeAuthorizedLocation());
      }
    } else {
      _stopDeviceWatch();
    }
  }

  void _showLocationAlert(LocationCapabilityStatus status) {
    if (!mounted) return;
    final message = switch (status) {
      LocationCapabilityStatus.permissionDenied =>
        'Accès à la position refusé.',
      LocationCapabilityStatus.settingsRequired =>
        'Autorisez la position dans les paramètres de l’application.',
      LocationCapabilityStatus.restricted =>
        'Localisation limitée par cet appareil.',
      LocationCapabilityStatus.serviceUnavailable =>
        'Activez la localisation du téléphone.',
      LocationCapabilityStatus.disabledByConfiguration =>
        'Localisation indisponible dans cette version.',
      LocationCapabilityStatus.failed =>
        'Impossible de mettre à jour votre position.',
      LocationCapabilityStatus.ready => 'Position disponible.',
    };
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        content: Text(message),
        action: status == LocationCapabilityStatus.settingsRequired
            ? SnackBarAction(
                label: 'Paramètres',
                onPressed: () => unawaited(_openLocationSettings()),
              )
            : null,
      ),
    );
  }

  Future<void> _openLocationSettings() async {
    final location = widget.location;
    if (location == null) return;
    try {
      await location.permissions.openSettings();
    } on Object {
      // The system controls settings navigation; the map stays usable.
    }
  }

  Future<void> _paintDevicePosition() {
    final controller = _mapController;
    final latitude = _deviceLatitude;
    final longitude = _deviceLongitude;
    if (controller == null || latitude == null || longitude == null) {
      return Future<void>.value();
    }
    final next = _deviceRender.then((_) async {
      if (!mounted || _mapController != controller) return;
      try {
        await controller.showDevicePosition(latitude, longitude);
      } on Object {
        // The already-admitted Discovery field remains usable.
      }
    });
    _deviceRender = next;
    return next;
  }

  Future<void> _startDeviceWatch() async {
    final location = widget.location;
    if (_deviceWatch?.stopped == true) _deviceWatch = null;
    if (!_trackingRequested ||
        location == null ||
        _deviceWatch != null ||
        _deviceWatchStarting) {
      return;
    }
    _deviceWatchStarting = true;
    final generation = ++_trackingGeneration;
    try {
      final result = await location.foregroundWatch(
        profile: LocationTrackingProfile.active,
        onFix: (fix) {
          if (!mounted || generation != _trackingGeneration) return;
          if (!fix.latitude.isFinite ||
              !fix.longitude.isFinite ||
              fix.latitude < -90 ||
              fix.latitude > 90 ||
              fix.longitude < -180 ||
              fix.longitude > 180) {
            return;
          }
          if (_deviceLatitude == fix.latitude &&
              _deviceLongitude == fix.longitude) {
            return;
          }
          _deviceLatitude = fix.latitude;
          _deviceLongitude = fix.longitude;
          unawaited(_paintDevicePosition());
        },
        onError: (_) {
          if (!mounted || generation != _trackingGeneration) return;
          _trackingRequested = false;
          _stopDeviceWatch();
          _showLocationAlert(LocationCapabilityStatus.failed);
        },
      );
      if (mounted &&
          generation == _trackingGeneration &&
          _trackingRequested &&
          result.started) {
        _deviceWatch = result.handle;
      } else {
        await result.handle?.stop();
        if (mounted &&
            generation == _trackingGeneration &&
            result.status != LocationCapabilityStatus.ready) {
          _trackingRequested = false;
          _showLocationAlert(result.status);
        }
      }
    } on Object {
      if (mounted && generation == _trackingGeneration) {
        _trackingRequested = false;
        _showLocationAlert(LocationCapabilityStatus.failed);
      }
    } finally {
      _deviceWatchStarting = false;
      // A pause/resume during permission acquisition must not lose the
      // foreground session; a failed session never auto-retries indefinitely.
      if (mounted &&
          _trackingRequested &&
          generation != _trackingGeneration &&
          _deviceWatch == null &&
          WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
        unawaited(_startDeviceWatch());
      }
    }
  }

  Future<void> _recenterOnDevice() async {
    final location = widget.location;
    final controller = _mapController;
    if (location == null || controller == null || _locationBusy) return;

    // Recenter immediately if the foreground stream has already supplied a
    // position. Recenter never requests an additional GPS fix unnecessarily.
    if (_deviceLatitude != null && _deviceLongitude != null) {
      _clearSelection();
      _trackingRequested = true;
      unawaited(_startDeviceWatch());
      try {
        await controller.moveTo(_deviceLatitude!, _deviceLongitude!);
      } on Object {
        // MapLibre can be reloading its style; GPS updates may continue.
      }
      return;
    }

    setState(() => _locationBusy = true);
    try {
      // First-time location acquisition remains explicit and bounded.
      final result = await location.current().timeout(
        const Duration(seconds: 8),
      );
      if (!mounted || location != widget.location) return;
      final fix = result.fix;
      if (!result.available || fix == null) {
        _showLocationAlert(result.status);
        return;
      }
      if (!fix.latitude.isFinite ||
          !fix.longitude.isFinite ||
          fix.latitude < -90 ||
          fix.latitude > 90 ||
          fix.longitude < -180 ||
          fix.longitude > 180) {
        _showLocationAlert(LocationCapabilityStatus.failed);
        return;
      }
      _deviceLatitude = fix.latitude;
      _deviceLongitude = fix.longitude;
      _trackingRequested = true;
      unawaited(_startDeviceWatch());
      _clearSelection();
      await _paintDevicePosition();
      await controller.moveTo(fix.latitude, fix.longitude);
    } on TimeoutException {
      if (mounted) {
        _showLocationAlert(LocationCapabilityStatus.failed);
      }
    } on Object {
      if (mounted) {
        _showLocationAlert(LocationCapabilityStatus.failed);
      }
    } finally {
      if (mounted) setState(() => _locationBusy = false);
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
      final focus = widget.initialMapFocus;
      final selected = anchors.where(
        (anchor) => anchor.candidateKey == _selectedCandidateKey,
      );
      if (focus != null) {
        await controller.focusLocation(focus.latitude, focus.longitude);
      } else if (selected.isNotEmpty) {
        await controller.focusLocation(
          selected.first.latitude,
          selected.first.longitude,
        );
      } else {
        // One point per actual location, with admitted possibility counts.
        // A dense neighbourhood should win the first camera viewport over
        // a distant outlier, without removing any points from the map.
        final byLocation = <String, DiscoveryMapPin>{};
        final countByLocation = <String, Set<String>>{};
        for (final anchor in anchors) {
          final key = '${anchor.latitude}:${anchor.longitude}';
          byLocation.putIfAbsent(
            key,
            () => DiscoveryMapPin(anchor.latitude, anchor.longitude),
          );
          countByLocation
              .putIfAbsent(key, () => <String>{})
              .add(anchor.candidateKey);
        }
        await controller.fitPins([
          for (final entry in byLocation.entries)
            DiscoveryMapPin(
              entry.value.latitude,
              entry.value.longitude,
              opportunityCount: countByLocation[entry.key]!.length,
            ),
        ]);
      }
    } on Object {
      _initialCameraPositioned = false;
    }
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _selectedCandidateKey = widget.initialSelectedCandidateKey;
    if (widget.initialFocusedAnchor?.candidateKey == _selectedCandidateKey) {
      _focusedAnchor = widget.initialFocusedAnchor;
    }
    if (_selectedCandidateKey != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_resolveSelected());
      });
    }
    // Existing Android permission is enough to show and update the GPS dot.
    // Never request permission automatically when Carte opens.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_resumeAuthorizedLocation());
    });
  }

  @override
  void didUpdateWidget(covariant DiscoverySpatialView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.location != widget.location ||
        oldWidget.mapConfig.enabled != widget.mapConfig.enabled) {
      _stopDeviceWatch();
      _trackingRequested = false;
      if (widget.mapConfig.enabled) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) unawaited(_resumeAuthorizedLocation());
        });
      }
    }
    if (oldWidget.detailRefreshRevision != widget.detailRefreshRevision &&
        _selectedCandidateKey != null) {
      ++_detailGeneration;
      _confirmedDetail = null;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _selectedCandidateKey != null) {
          unawaited(_resolveSelected());
        }
      });
    }
    if (oldWidget.initialSelectedCandidateKey !=
        widget.initialSelectedCandidateKey) {
      ++_detailGeneration;
      _selectedCandidateKey = widget.initialSelectedCandidateKey;
      _focusedAnchor =
          widget.initialFocusedAnchor?.candidateKey == _selectedCandidateKey
          ? widget.initialFocusedAnchor
          : null;
      _confirmedDetail = null;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          if (_selectedCandidateKey != null) unawaited(_resolveSelected());
          unawaited(
            _displayPins(
              _selector.spatialAnchorsFromCollection(
                widget.selection.collection,
              ),
            ),
          );
        }
      });
    }
    final keys = widget.selection.collection.items
        .map((item) => item.candidateKey)
        .toSet();
    final spatialChanged =
        widget.showMapOnCompact && widget.spatialRevision != null
        ? oldWidget.spatialRevision != widget.spatialRevision
        : oldWidget.selection.collection.items !=
              widget.selection.collection.items;
    if (spatialChanged) {
      ++_detailGeneration;
      _confirmedDetail = null;
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
      _focusedAnchor = null;
      _confirmedDetail = null;
      widget.onSelectionChanged?.call(null);
      widget.onFocusedAnchorChanged?.call(null);
      unawaited(
        _displayPins(
          _selector.spatialAnchorsFromCollection(widget.selection.collection),
        ),
      );
    }
  }

  String? _placeForSelection(
    DiscoveryItemPresentation item,
    DiscoverySpatialAnchor? anchor,
  ) {
    final place = anchor?.fact['place'];
    if (place is! Map) return item.place;
    final name = place['name'];
    final locality = place['locality'];
    final label = name is String && name.trim().isNotEmpty
        ? name.trim()
        : locality is String && locality.trim().isNotEmpty
        ? locality.trim()
        : item.place;
    if (label == null) return null;
    const roles = {
      'departure': 'Départ',
      'arrival': 'Arrivée',
      'stopover': 'Escale',
      'boarding': 'Embarquement',
      'dropoff': 'Débarquement',
    };
    final role = roles[anchor?.fact['role']];
    return role == null ? label : '$role · $label';
  }

  DiscoveryItemPresentation? get _selectedItem {
    final items = widget.selection.collection.items;
    if (items.isEmpty) return null;
    final key = _selectedCandidateKey;
    if (key != null) {
      for (final item in items) {
        if (item.candidateKey == key &&
            _selector
                .spatialAnchorsFromCollection(widget.selection.collection)
                .any((anchor) => anchor.candidateKey == key)) {
          return item;
        }
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
      final focused = _focusedAnchor;
      if (focused != null && focused.candidateKey == selected.candidateKey) {
        for (final point in points) {
          if (point.candidateKey == focused.candidateKey &&
              point.latitude == focused.latitude &&
              point.longitude == focused.longitude &&
              point.fact['role'] == focused.fact['role']) {
            selectedPoint = point;
            break;
          }
        }
      }
      if (selectedPoint == null) {
        for (final point in points) {
          if (point.candidateKey == selected.candidateKey) {
            selectedPoint = point;
            break;
          }
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
              onFeatureTap: (point, _) => unawaited(_onMapFeatureTap(point)),
              onStyleReady: () => unawaited(_onStyleReady(points)),
              config: widget.mapConfig,
              onViewportChanged: widget.onViewportChanged,
              initialViewport:
                  widget.restoredViewport ??
                  MapViewport(
                    center:
                        widget.initialMapFocus ??
                        (anchor == null
                            ? const MapCoordinate(0, 0)
                            : MapCoordinate(anchor.latitude, anchor.longitude)),
                    zoom: widget.initialMapFocus != null || anchor != null
                        ? 11
                        : 1,
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
              widget.selection.surface.availability ==
                  MakoloAvailabilityCue.empty)
            Positioned(
              top: 72,
              left: MakoloSpacing.sm,
              right: MakoloSpacing.sm,
              child: Center(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(MakoloSpacing.sm),
                    child: Text(
                      'Aucune opportunité sur la carte',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                ),
              ),
            ),
          if (selected != null ||
              (widget.location != null && widget.mapConfig.enabled))
            Positioned(
              left: MakoloSpacing.sm,
              right: MakoloSpacing.sm,
              bottom: MediaQuery.paddingOf(context).bottom + MakoloSpacing.sm,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  if (widget.location != null && widget.mapConfig.enabled)
                    Material(
                      elevation: 2,
                      shape: const CircleBorder(),
                      color: Theme.of(context).colorScheme.surface,
                      child: IconButton(
                        tooltip: 'Me localiser',
                        onPressed: _locationBusy
                            ? null
                            : () => unawaited(_recenterOnDevice()),
                        icon: _locationBusy
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.my_location_rounded),
                      ),
                    ),
                  if (selected != null) ...[
                    if (widget.location != null && widget.mapConfig.enabled)
                      const SizedBox(height: MakoloSpacing.sm),
                    ConstrainedBox(
                      constraints: BoxConstraints(
                        maxHeight: MediaQuery.sizeOf(context).height * 0.38,
                      ),
                      child: _DiscoveryMapPreview(
                        item: selected,
                        place: _placeForSelection(selected, selectedPoint),
                        detail: widget.allowOwnerActions
                            ? _confirmedDetail
                            : null,
                        saving: _savingSelected,
                        onClose: _clearSelection,
                        onOpen: () => widget.onOpen(selected),
                        onDirections:
                            selectedPoint == null || widget.onDirections == null
                            ? null
                            : () => widget.onDirections!(selectedPoint!),
                        onSave: widget.onSave == null
                            ? null
                            : () => unawaited(_saveSelected()),
                        shareApi: widget.shareApi,
                        shareAuthenticated: widget.shareAuthenticated,
                        collectiveReadOnly: widget.collectiveReadOnly,
                        baseUri: widget.baseUri,
                      ),
                    ),
                  ],
                ],
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
                    const MakoloCardSkeleton(
                      kind: MakoloCardSkeletonKind.discover,
                      count: 1,
                    ),
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
        title: 'Ce contenu n’est pas disponible.',
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
        title: 'Découvrir n’est pas accessible pour le moment.',
        actionLabel: onRetry == null ? null : 'Réessayer',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.offlineNoSnapshot) ||
        states.contains(DiscoveryFieldState.offlineWithSnapshot)) {
      return _EmptyBody(
        icon: Icons.info_outline_rounded,
        title: 'Recherche momentanément indisponible.',
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
      title: 'Rien à découvrir pour le moment.',
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
        MakoloActionButton(
          label: 'Précédent',
          appearance: MakoloActionAppearance.secondary,
          onPressed: collection.page > 1 && onPage != null
              ? () => onPage!(collection.page - 1)
              : null,
          icon: Icons.chevron_left_rounded,
        ),
        const Spacer(),
        Text(
          'Page ${collection.page}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const Spacer(),
        MakoloActionButton(
          label: 'Suivant',
          appearance: MakoloActionAppearance.primary,
          onPressed: collection.hasNext && onPage != null
              ? () => onPage!(collection.page + 1)
              : null,
          icon: Icons.chevron_right_rounded,
        ),
      ],
    );
  }
}
