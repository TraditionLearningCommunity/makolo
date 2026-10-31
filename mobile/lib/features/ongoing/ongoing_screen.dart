import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../data/local/profile_store.dart';
import '../../data/files/profile_recognition_image_store.dart';
import '../../app/sync_lifecycle.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/refresh_boundary.dart';
import '../../navigation/deep_link_resolver.dart';
import '../../navigation/destination.dart';
import '../../presentation/humanization.dart';
import '../../presentation/media/retained_recognition_image.dart';
import '../../repositories/personal_repository.dart';
import '../../network/makolo_api_client.dart';
import '../discovery/discovery_repository.dart';
import '../discovery/discovery_selector.dart';
import '../discovery/discovery_share_sheet.dart';
import '../../presentation/possibilities/discovery_save_icon.dart';
import '../../presentation/possibilities/discovery_reader.dart';
import 'ongoing_presentation.dart';

class OngoingScreen extends StatefulWidget {
  const OngoingScreen({
    super.key,
    required this.repository,
    this.projectionStream,
    this.baseUri,
    this.api,
    this.discovery,
    this.initialContinuityId,
  });
  final PersonalRepository repository;
  final Stream<StoredProjection?>? projectionStream;
  final Uri? baseUri;
  final MakoloApiClient? api;
  final DiscoveryRepository? discovery;
  final String? initialContinuityId;
  @override
  State<OngoingScreen> createState() => _OngoingScreenState();
}

class _OngoingScreenState extends State<OngoingScreen> {
  String? _selectedOwnerKey;
  StoredProjection? _lastProjection;
  bool _loadingMore = false;
  String? _moreError;
  late Stream<StoredProjection?> _projectionStream;
  late Stream<OwnerSourceState> _sourceStream;

  @override
  void initState() {
    super.initState();
    _selectedOwnerKey = widget.initialContinuityId;
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant OngoingScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialContinuityId != widget.initialContinuityId) {
      _selectedOwnerKey = widget.initialContinuityId;
    }
    if (oldWidget.repository != widget.repository ||
        oldWidget.projectionStream != widget.projectionStream) {
      _lastProjection = null;
      _loadingMore = false;
      _moreError = null;
      _bindStreams();
    }
  }

  void _bindStreams() {
    _projectionStream =
        widget.projectionStream ?? widget.repository.watchOngoing();
    _sourceStream = widget.projectionStream == null
        ? widget.repository.watchOngoingSource()
        : const Stream<OwnerSourceState>.empty();
  }

  void _select(OngoingContinuityPresentation item) =>
      setState(() => _selectedOwnerKey = _ownerKey(item));
  void _clearSelection() => setState(() => _selectedOwnerKey = null);

  String _ownerKey(OngoingContinuityPresentation item) => item.id;

  String? _profileId() {
    try {
      return widget.repository.store.profileId;
    } on Object {
      // Presentation-only test repositories may not have device storage.
      // No private file is written without a known Profile scope.
      return null;
    }
  }

  Future<void> _setSaved(
    OngoingPossibilityPresentation action,
    bool saved,
  ) async {
    final discovery = widget.discovery;
    if (discovery == null) throw StateError('Discovery unavailable');
    await discovery.setSaved(
      family: action.family,
      id: action.id,
      saved: saved,
    );
    await widget.repository.reflectOngoingDiscoverySave(
      activityId: action.id,
      saved: saved,
    );
  }

  Future<void> _loadMore() async {
    final current = _lastProjection;
    final api = widget.api;
    if (_loadingMore || current == null || api == null) return;
    setState(() {
      _loadingMore = true;
      _moreError = null;
    });
    try {
      await widget.repository.loadMoreOngoing(api: api, current: current);
    } on Object {
      if (mounted) {
        setState(() => _moreError = 'La suite n’a pas pu être chargée.');
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: StreamBuilder<OwnerSourceState>(
      stream: _sourceStream,
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) => StreamBuilder<StoredProjection?>(
        stream: _projectionStream,
        builder: (context, snapshot) {
          if (!snapshot.hasError &&
              snapshot.connectionState == ConnectionState.active) {
            _lastProjection = snapshot.data;
          }
          final projection = snapshot.data ?? _lastProjection;
          final syncStatus = SyncStatusScope.maybeOf(context);
          if (projection == null &&
              (snapshot.hasError ||
                  sourceSnapshot.hasError ||
                  sourceSnapshot.data?.lastErrorCode != null ||
                  syncStatus?.state == SyncVisualState.failed)) {
            return MakoloErrorState(
              message: 'En cours indisponible.',
              preservedMessage: '',
              onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
            );
          }
          if (projection == null &&
              (syncStatus?.state == SyncVisualState.syncing ||
                  snapshot.connectionState == ConnectionState.waiting)) {
            return const MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.loading,
              ),
              content: SizedBox.shrink(),
            );
          }
          if (projection == null) {
            return const MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.empty,
              ),
              empty: MakoloEmptyState(
                title: 'En cours indisponible.',
                body: 'Vos informations ne sont pas encore disponibles sur cet appareil.',
              ),
              content: SizedBox.shrink(),
            );
          }
          final items = OngoingContinuityPresentation.fromProjection(
            projection,
          );
          if (items.isEmpty) {
            return MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.empty,
                failure: sourceSnapshot.data?.lastErrorCode == null
                    ? MakoloFailureCue.none
                    : MakoloFailureCue.recoverable,
              ),
              recoverableErrorMessage: 'Actualisation impossible.',
              preservedMessage: '',
              onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
              empty: const MakoloEmptyState(
                title: 'Rien en cours pour le moment.',
              ),
              content: const SizedBox.shrink(),
            );
          }
          final matches = items.where(
            (item) => _ownerKey(item) == _selectedOwnerKey,
          );
          final selected = matches.isEmpty ? null : matches.first;
          final cursor = projection.payload['continuation'];
          final moreToken = cursor is Map ? cursor['token'] : null;
          final stale =
              projection.freshUntil != null &&
              projection.freshUntil!.isBefore(DateTime.now().toUtc());
          return MakoloSurfaceStateView(
            state: MakoloSurfacePresentation(
              availability: MakoloAvailabilityCue.content,
              freshness: stale
                  ? MakoloFreshnessCue.oldObservation
                  : MakoloFreshnessCue.current,
              failure:
                  snapshot.hasError ||
                      sourceSnapshot.data?.lastErrorCode != null
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
            ),
            // Keep existing journeys visible without an additional banner.
            recoverableErrorMessage: null,
            preservedMessage: '',
            onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
            content: _OngoingAdaptiveView(
              profileId: _profileId(),
              items: items,
              selected: selected,
              stale: stale,
              onSelect: _select,
              onBack: _clearSelection,
              baseUri: widget.baseUri,
              api: widget.api,
              onSave: widget.discovery == null ? null : _setSaved,
              onMore:
                  widget.api != null &&
                      moreToken is String &&
                      moreToken.isNotEmpty
                  ? () {
                      _loadMore();
                    }
                  : null,
              moreBusy: _loadingMore,
              moreError: _moreError,
              endReached: cursor is Map && cursor['state'] == 'end',
            ),
          );
        },
      ),
    ),
  );
}

class _OngoingAdaptiveView extends StatelessWidget {
  const _OngoingAdaptiveView({
    required this.profileId,
    required this.items,
    required this.selected,
    required this.stale,
    required this.onSelect,
    required this.onBack,
    this.baseUri,
    this.api,
    this.onSave,
    this.onMore,
    this.moreBusy = false,
    this.moreError,
    this.endReached = false,
  });
  final String? profileId;
  final List<OngoingContinuityPresentation> items;
  final OngoingContinuityPresentation? selected;
  final bool stale;
  final ValueChanged<OngoingContinuityPresentation> onSelect;
  final VoidCallback onBack;
  final Uri? baseUri;
  final MakoloApiClient? api;
  final Future<void> Function(OngoingPossibilityPresentation, bool)? onSave;
  final VoidCallback? onMore;
  final bool moreBusy;
  final String? moreError;
  final bool endReached;

  @override
  Widget build(BuildContext context) => MakoloContentFrame(
    maxContentWidth: selected == null ? MakoloLayout.calmMaxWidth : 1040,
    horizontalPadding: MediaQuery.sizeOf(context).width < 600 ? 0 : null,
    child: selected == null
        ? _OngoingField(
            profileId: profileId,
            items: items,
            selected: selected,
            stale: stale,
            onSelect: onSelect,
            baseUri: baseUri,
            api: api,
            onSave: onSave,
            onMore: onMore,
            moreBusy: moreBusy,
            moreError: moreError,
            endReached: endReached,
          )
        : MakoloAdaptiveSplit(
            splitAt: MakoloLayout.ongoingSplitMinWidth,
            field: _OngoingField(
              profileId: profileId,
              items: items,
              selected: selected,
              stale: stale,
              onSelect: onSelect,
              baseUri: baseUri,
              api: api,
              onSave: onSave,
              onMore: onMore,
              moreBusy: moreBusy,
              moreError: moreError,
              endReached: endReached,
            ),
            focus: selected == null
                ? const _OngoingFocusPlaceholder()
                : _OngoingFocus(
                    profileId: profileId,
                    item: selected!,
                    onBack: onBack,
                    stale: stale,
                    api: api,
                    baseUri: baseUri,
                  ),
            narrow: selected == null
                ? _OngoingField(
                    profileId: profileId,
                    items: items,
                    selected: selected,
                    stale: stale,
                    onSelect: onSelect,
                    baseUri: baseUri,
                    api: api,
                    onSave: onSave,
                    onMore: onMore,
                    moreBusy: moreBusy,
                    moreError: moreError,
                    endReached: endReached,
                  )
                : _OngoingFocus(
                    profileId: profileId,
                    item: selected!,
                    onBack: onBack,
                    stale: stale,
                    api: api,
                    baseUri: baseUri,
                  ),
          ),
  );
}

class _OngoingField extends StatefulWidget {
  const _OngoingField({
    required this.profileId,
    required this.items,
    required this.selected,
    required this.stale,
    required this.onSelect,
    this.baseUri,
    this.api,
    this.onSave,
    this.onMore,
    this.moreBusy = false,
    this.moreError,
    this.endReached = false,
  });

  final String? profileId;
  final List<OngoingContinuityPresentation> items;
  final OngoingContinuityPresentation? selected;
  final bool stale;
  final ValueChanged<OngoingContinuityPresentation> onSelect;
  final Uri? baseUri;
  final MakoloApiClient? api;
  final Future<void> Function(OngoingPossibilityPresentation, bool)? onSave;
  final VoidCallback? onMore;
  final bool moreBusy;
  final String? moreError;
  final bool endReached;

  @override
  State<_OngoingField> createState() => _OngoingFieldState();
}

class _OngoingFieldState extends State<_OngoingField> {
  final ScrollController _scroll = ScrollController();
  final Set<String> _expanded = <String>{};

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_maybeMore);
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeMore());
  }

  @override
  void didUpdateWidget(covariant _OngoingField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.items.length != widget.items.length ||
        oldWidget.moreBusy != widget.moreBusy ||
        oldWidget.moreError != widget.moreError) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeMore());
    }
  }

  void _maybeMore() {
    if (!mounted ||
        !_scroll.hasClients ||
        widget.moreBusy ||
        widget.moreError != null ||
        widget.onMore == null) {
      return;
    }
    if (_scroll.position.extentAfter < 480) widget.onMore?.call();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView.separated(
    controller: _scroll,
    key: const PageStorageKey<String>('ongoing-field'),
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
    itemCount: widget.items.length + 1,
    // Like Discover, the breathing space must be visibly distinct from
    // the unit canvas, not just an invisible gap of the same background.
    // Only separate actual continuities, never the pagination sentinel.
    separatorBuilder: (context, index) => index < widget.items.length - 1
        ? ColoredBox(
            key: const Key('ongoing-unit-gutter'),
            color: context.makoloSurfaces.surface,
            child: const SizedBox(height: MakoloSpacing.sm),
          )
        : const SizedBox.shrink(),
    itemBuilder: (context, index) {
      if (index == widget.items.length) {
        if (widget.moreError != null) {
          return Center(
            child: TextButton.icon(
              onPressed: widget.onMore,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Réessayer'),
            ),
          );
        }
        if (widget.moreBusy) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(MakoloSpacing.md),
              child: CircularProgressIndicator.adaptive(),
            ),
          );
        }
        if (widget.endReached && !widget.stale && widget.items.isNotEmpty) {
          return const SizedBox.shrink();
        }
        return const SizedBox(height: MakoloSpacing.xl);
      }
      final item = widget.items[index];
      final expanded = _expanded.contains(item.id);
      final hasDetail = _ongoingVisibleDetailGroups(item).isNotEmpty;
      // Keep one continuity, its recognition media, details and commands
      // within the same visual boundary. The actions always close the unit.
      return DecoratedBox(
        key: ValueKey<String>('ongoing-unit-${item.id}'),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _OngoingRow(
              profileId: widget.profileId,
              item: item,
              selected: item.id == widget.selected?.id,
              stale: widget.stale,
              onTap: () => widget.onSelect(item),
              baseUri: widget.baseUri,
              api: widget.api,
            ),
            if (item.resources.isNotEmpty)
              _OngoingResourceList(
                item: item,
                baseUri: widget.baseUri,
                compact: true,
              ),
            if (hasDetail) ...[
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton.icon(
                  onPressed: () => setState(() {
                    if (!_expanded.add(item.id)) _expanded.remove(item.id);
                  }),
                  icon: Icon(
                    expanded
                        ? Icons.expand_less_rounded
                        : Icons.expand_more_rounded,
                  ),
                  label: Text(expanded ? 'Voir moins' : 'Voir plus'),
                ),
              ),
              if (expanded) _OngoingN1Details(item: item),
            ],
            _OngoingN1Actions(
              key: ValueKey<String>('ongoing-actions-${item.id}'),
              item: item,
              api: widget.api,
              baseUri: widget.baseUri,
              onSave: widget.onSave,
            ),
          ],
        ),
      );
    },
  );
}

/// One resource treatment for N1 and N2. All destinations are owner-backed:
/// public Activity resources use the existing Discovery reader; private
/// JourneyArtifacts hand off to the authorized Journey route.
class _OngoingResourceList extends StatefulWidget {
  const _OngoingResourceList({
    required this.item,
    required this.baseUri,
    required this.compact,
  });

  final OngoingContinuityPresentation item;
  final Uri? baseUri;
  final bool compact;

  @override
  State<_OngoingResourceList> createState() => _OngoingResourceListState();
}

class _OngoingResourceListState extends State<_OngoingResourceList> {
  bool _showAll = false;

  Uri? _destination(Map<String, dynamic> resource) {
    final kind = resource['kind'];
    final source = switch (kind) {
      'file' => resource['download_url'],
      'text' => resource['read_url'],
      'url' => resource['external_url'],
      _ => null,
    };
    if (source is! String || source.trim().isEmpty) return null;
    if (kind == 'url') {
      final uri = Uri.tryParse(source.trim());
      return discoverySafeDestination(uri) && uri!.userInfo.isEmpty
          ? uri
          : null;
    }
    final resolved = ongoingRecognitionImageUrl(source, widget.baseUri);
    return resolved == null ? null : Uri.parse(resolved);
  }

  bool _canOpen(Map<String, dynamic> resource) {
    if (resource['kind'] == 'journey_artifact') {
      return _OngoingN1Details.routeFor(widget.item) != null;
    }
    if (resource['kind'] == 'text' &&
        (resource['text_content']?.toString().trim().isNotEmpty ?? false)) {
      return true;
    }
    return _destination(resource) != null;
  }

  Future<void> _open(Map<String, dynamic> resource) async {
    if (!_canOpen(resource)) return;
    if (resource['kind'] == 'journey_artifact') {
      final path = _OngoingN1Details.routeFor(widget.item);
      if (path != null && mounted) context.push(path);
      return;
    }
    final title = (resource['title'] ?? 'Ressource').toString();
    final text =
        resource['kind'] == 'text' && resource['text_content'] is String
        ? (resource['text_content'] as String).trim()
        : '';
    // A published text has a canonical read URL whenever the server supplies
    // one. If only already-authorized inline content is available offline,
    // keep the *same* native reader and its copy/share/export controls.
    final uri = _destination(resource);
    if (uri == null && text.isEmpty) return;
    if (!mounted) return;
    if (resource['kind'] == 'url' && uri != null) {
      try {
        final opened = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
        if (!opened && mounted) _openFailure();
      } on Object {
        if (mounted) _openFailure();
      }
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => DiscoveryReader(
          items: [
            DiscoveryReaderItem(
              title: title,
              uri: uri ?? Uri(),
              inlineText: uri == null && text.isNotEmpty ? text : null,
              mimeType: resource['kind'] == 'text'
                  ? 'text/plain'
                  : (resource['mime_type']?.toString().trim().isNotEmpty ??
                        false)
                  ? resource['mime_type'].toString()
                  : 'application/octet-stream',
            ),
          ],
        ),
      ),
    );
  }

  void _openFailure() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Cette ressource ne peut pas être ouverte.'),
      ),
    );
  }

  IconData _icon(Map<String, dynamic> resource) {
    final kind = resource['kind'];
    final mime = (resource['mime_type'] ?? '').toString().toLowerCase();
    if (kind == 'url') return Icons.language_rounded;
    if (mime.startsWith('image/')) return Icons.image_outlined;
    if (mime.startsWith('video/')) return Icons.movie_outlined;
    if (mime.startsWith('audio/')) return Icons.audiotrack_outlined;
    if (mime == 'application/pdf') return Icons.picture_as_pdf_outlined;
    if (kind == 'text' || mime.startsWith('text/')) {
      return Icons.article_outlined;
    }
    return Icons.description_outlined;
  }

  @override
  Widget build(BuildContext context) {
    final entries = <Map<String, dynamic>>[];
    final seen = <String>{};
    for (final resource in widget.item.resources) {
      final title = resource['title'];
      if (title is! String || title.trim().isEmpty) continue;
      final identity = resource['id']?.toString() ?? title.trim();
      if (seen.add(identity)) entries.add(resource);
    }
    if (entries.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final muted = theme.colorScheme.onSurfaceVariant;
    final shown = widget.compact && !_showAll ? entries.take(2) : entries;
    return Padding(
      key: Key(
        widget.compact ? 'ongoing-n1-resources' : 'ongoing-n2-resources',
      ),
      padding: EdgeInsets.fromLTRB(
        widget.compact ? 14 : 0,
        MakoloSpacing.sm,
        widget.compact ? 14 : 0,
        MakoloSpacing.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Documents et ressources', style: theme.textTheme.titleSmall),
          const SizedBox(height: MakoloSpacing.sm),
          for (final resource in shown)
            Padding(
              padding: const EdgeInsets.only(bottom: MakoloSpacing.xs),
              child: InkWell(
                key: ValueKey(
                  'ongoing-resource-${resource['id'] ?? resource['title']}',
                ),
                onTap: _canOpen(resource) ? () => _open(resource) : null,
                borderRadius: BorderRadius.circular(MakoloRadii.small),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: 48),
                  child: Row(
                    children: [
                      Icon(_icon(resource), size: 20, color: muted),
                      const SizedBox(width: MakoloSpacing.sm),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              resource['title'].toString(),
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: _canOpen(resource)
                                    ? theme.colorScheme.primary
                                    : theme.colorScheme.onSurface,
                                fontWeight: _canOpen(resource)
                                    ? FontWeight.w600
                                    : FontWeight.normal,
                              ),
                            ),
                            if (resource['description'] is String &&
                                (resource['description'] as String)
                                    .trim()
                                    .isNotEmpty)
                              Text(
                                resource['description'] as String,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: muted,
                                ),
                              ),
                          ],
                        ),
                      ),
                      if (_canOpen(resource)) ...[
                        const SizedBox(width: MakoloSpacing.xs),
                        Icon(
                          Icons.chevron_right_rounded,
                          size: 18,
                          color: muted,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          if (widget.compact && entries.length > 2)
            TextButton(
              onPressed: () => setState(() => _showAll = !_showAll),
              child: Text(
                _showAll
                    ? 'Voir moins de ressources'
                    : 'Voir les ${entries.length} ressources',
              ),
            ),
        ],
      ),
    );
  }
}

/// The three useful commands share the existing Discovery and Sharing owners.
class _OngoingN1Actions extends StatefulWidget {
  const _OngoingN1Actions({
    super.key,
    required this.item,
    this.api,
    this.baseUri,
    this.onSave,
  });
  final OngoingContinuityPresentation item;
  final MakoloApiClient? api;
  final Uri? baseUri;
  final Future<void> Function(OngoingPossibilityPresentation, bool)? onSave;

  @override
  State<_OngoingN1Actions> createState() => _OngoingN1ActionsState();
}

class _OngoingN1ActionsState extends State<_OngoingN1Actions> {
  bool _busy = false;
  bool? _confirmedSaved;

  @override
  void didUpdateWidget(covariant _OngoingN1Actions oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.possibility?.savedState !=
            widget.item.possibility?.savedState ||
        oldWidget.item.possibility?.id != widget.item.possibility?.id) {
      _confirmedSaved = null;
    }
  }

  Future<void> _save() async {
    final action = widget.item.possibility;
    if (_busy || action == null || !action.canSave || widget.onSave == null) {
      return;
    }
    setState(() => _busy = true);
    try {
      final saved = !(_confirmedSaved ?? (action.savedState == 'saved'));
      await widget.onSave!(action, saved);
      if (mounted) setState(() => _confirmedSaved = saved);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Enregistrement non confirmé. Réessayez.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final possibility = widget.item.possibility;
    final route = _OngoingN1Details.routeFor(widget.item);
    final label = switch (widget.item.kind) {
      'waitlist' when widget.item.capabilities.contains('accept') => 'Répondre',
      'transfer' when widget.item.capabilities.contains('accept') => 'Répondre',
      'access' => 'Voir mon accès',
      'dossier' => 'Ouvrir le dossier',
      'project' => 'Voir le projet',
      'waitlist' => 'Suivre ma liste',
      'payment' => 'Suivre le paiement',
      'transfer' => 'Voir le transfert',
      'funding' => 'Gérer',
      _ => 'Continuer',
    };
    final canShare = possibility?.canShare == true && widget.api != null;
    final sharedItem = canShare
        ? DiscoveryItemPresentation(
            family: possibility!.family,
            id: possibility.id,
            candidateKey: 'ongoing:${possibility.id}',
            title: widget.item.title,
            summary: widget.item.synthesis,
            capabilities: const <String>{},
            links: {'web_share': possibility.shareUrl!},
            savedState: possibility.savedState,
          )
        : null;
    final saved = _confirmedSaved ?? (possibility?.savedState == 'saved');
    final canSave = possibility?.canSave == true && widget.onSave != null;

    // A calm continuity needs no empty toolbar when no operation exists.
    if (!canSave && !canShare && route == null) {
      return const SizedBox.shrink();
    }

    // Match Discover's balanced three-icon action strip. No permanent
    // text labels or oversized middle button on the compact surface.
    return Column(
      children: [
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: MakoloSpacing.xs,
            vertical: MakoloSpacing.xs,
          ),
          child: Row(
            key: const Key('ongoing-n1-discover-actions'),
            children: [
              if (canSave)
                Expanded(
                  child: IconButton(
                    key: const Key('ongoing-n1-save'),
                    onPressed: _busy ? null : _save,
                    tooltip: saved ? 'Enregistré' : 'Enregistrer',
                    icon: _busy
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : DiscoveryOrbitIcon(
                            saved: saved,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                  ),
                ),
              if (route != null)
                Expanded(
                  child: IconButton(
                    key: const Key('ongoing-n1-primary'),
                    onPressed: () => context.push(route),
                    tooltip: label,
                    icon: const Icon(Icons.play_circle_outline_rounded),
                  ),
                ),
              if (sharedItem != null)
                Expanded(
                  child: DiscoveryShareControl(
                    item: sharedItem,
                    api: widget.api,
                    authenticated: true,
                    iconOnly: true,
                    baseUri: widget.baseUri,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _OngoingN1Details extends StatelessWidget {
  const _OngoingN1Details({required this.item});
  final OngoingContinuityPresentation item;

  static String? routeFor(OngoingContinuityPresentation item) {
    final kind = item.ownerKind;
    final id = item.ownerId;
    if (kind == null || id == null) return null;
    final chunks = id.split('-');
    if (chunks.length != 5 ||
        chunks[0].length != 8 ||
        chunks[1].length != 4 ||
        chunks[2].length != 4 ||
        chunks[3].length != 4 ||
        chunks[4].length != 12 ||
        id
            .replaceAll('-', '')
            .split('')
            .any(
              (character) => !'0123456789abcdefABCDEF'.contains(character),
            )) {
      return null;
    }
    // A decision is owned by Maintenant. N1 only hands off to the native
    // decision surface; it never issues accept/decline or replays a mutation.
    if ((kind == 'waitlist' || kind == 'ticket_transfer') &&
        item.capabilities.contains('accept')) {
      return '/now';
    }
    final canOpen =
        item.capabilities.contains('open_detail') ||
        (kind == 'access' && item.capabilities.contains('open_access'));
    if (!canOpen) return null;
    return const DeepLinkResolver().resolve(
      StructuredDestination(kind: kind, id: Uri.encodeComponent(id)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final groups = _ongoingVisibleDetailGroups(item);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, MakoloSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final (label, values) in groups) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(label, style: Theme.of(context).textTheme.titleSmall),
            for (final value in values)
              Padding(
                padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                child: Text(
                  value,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
          ],
        ],
      ),
    );
  }
}

// Deduplicate before rendering headings: an empty section must never appear.
List<(String, List<String>)> _ongoingVisibleDetailGroups(
  OngoingContinuityPresentation item,
) {
  final groups = <(String, List<String>)>[
    ('Déjà réglé', item.settled),
    ('De votre côté', item.mySide),
    ('En attente', item.elsewhere),
    ('Préparé par Makolo', item.makolo),
    ('À venir', item.systemOrTime),
    ('À suivre', item.next),
    if (item.blocker != null) ('Ce qui bloque', [item.blocker!]),
    if (item.unknown != null) ('À vérifier', [item.unknown!]),
  ];
  final seen = <String>{_ongoingKey(item.title), _ongoingKey(item.synthesis)};
  final visible = <(String, List<String>)>[];
  for (final (heading, entries) in groups) {
    final useful = <String>[];
    for (final entry in entries) {
      final value = entry.trim();
      if (value.isNotEmpty &&
          !_ongoingRedundant(value, item) &&
          seen.add(_ongoingKey(value))) {
        useful.add(value);
      }
    }
    if (useful.isNotEmpty) visible.add((heading, useful));
  }
  return visible;
}

String _ongoingKey(String value) => value
    .trim()
    .toLowerCase()
    .replaceAll(RegExp(r'\s+'), ' ')
    .replaceAll(RegExp(r'[.:;–—-]+$'), '')
    .trim();

bool _sameOngoingText(String? left, String? right) {
  if (left == null || right == null) return false;
  return _ongoingKey(left) == _ongoingKey(right);
}

String? _ongoingSummary(String title, String synthesis) {
  final value = synthesis.trim();
  if (value.isEmpty || _sameOngoingText(value, title)) return null;
  for (final entry in const <(String, String)>[
    ('confirmer :', 'À confirmer'),
    ('confirmer:', 'À confirmer'),
    ('vérifier :', 'À vérifier'),
    ('vérifier:', 'À vérifier'),
  ]) {
    if (value.toLowerCase().startsWith(entry.$1)) {
      final tail = value.substring(entry.$1.length).trim();
      if (_sameOngoingText(tail, title)) return entry.$2;
    }
  }
  return value;
}

bool _ongoingRedundant(String value, OngoingContinuityPresentation item) {
  if (_sameOngoingText(value, item.title) ||
      _sameOngoingText(value, item.synthesis)) {
    return true;
  }
  final reduced = _ongoingSummary(item.title, value);
  return reduced == 'À confirmer' || reduced == 'À vérifier';
}

/// Published N1 images are delivered by the same API origin that owns the
/// projection. No third-party tracking URL or client-generated picture.
String? ongoingRecognitionImageUrl(String? source, Uri? baseUri) {
  final value = source?.trim();
  if (value == null || value.isEmpty) return null;
  final raw = Uri.tryParse(value);
  if (raw == null) return null;
  final resolved = raw.hasScheme ? raw : baseUri?.resolveUri(raw);
  if (resolved == null ||
      (resolved.scheme != 'http' && resolved.scheme != 'https') ||
      resolved.host.isEmpty ||
      (baseUri != null && resolved.origin != baseUri.origin)) {
    return null;
  }
  return resolved.toString();
}

class _OngoingProtectedImage extends StatelessWidget {
  const _OngoingProtectedImage({
    super.key,
    required this.api,
    required this.profileId,
    required this.imageUrl,
    required this.label,
  });

  final MakoloApiClient api;
  final String? profileId;
  final String imageUrl;
  final String label;

  @override
  Widget build(BuildContext context) => RetainedRecognitionImage(
    api: api,
    profileId: profileId,
    path: Uri.parse(imageUrl).path,
    alt: label,
    placeholder: const Center(child: Icon(Icons.image_not_supported_outlined)),
  );
}

/// Recognition media is selected only from the public published media
/// projection. Its bytes still pass through the authenticated Makolo API;
/// the shared Discovery reader owns zoom, offline copy, export and sharing.
void _openOngoingProtectedMedia(
  BuildContext context, {
  required MakoloApiClient api,
  required String? profileId,
  required String imageUrl,
  required String title,
  required String mimeType,
}) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => DiscoveryReader(
        items: [
          DiscoveryReaderItem(
            title: title,
            uri: Uri.parse(imageUrl),
            mimeType: mimeType,
            authorizedImageBytes: () async {
              final path = Uri.parse(imageUrl).path;
              final retained = profileId == null
                  ? null
                  : await ProfileRecognitionImageStore(profileId: profileId)
                        .read(path);
              return retained ?? api.getPresentationImage(path);
            },
          ),
        ],
      ),
    ),
  );
}

/// G06 mobile: the same open, vertical reading rhythm as Discover.
/// A recognition image gets the available width; text never sits beside it.
class _OngoingRow extends StatelessWidget {
  const _OngoingRow({
    required this.profileId,
    required this.item,
    required this.selected,
    required this.stale,
    required this.onTap,
    this.baseUri,
    this.api,
  });

  final String? profileId;
  final OngoingContinuityPresentation item;
  final bool selected;
  final bool stale;
  final VoidCallback onTap;
  final Uri? baseUri;
  final MakoloApiClient? api;

  String? _supportingLine() {
    final candidate =
        item.supporting ??
        (item.mySide.isNotEmpty
            ? item.mySide.first
            : item.next.isNotEmpty
            ? item.next.first
            : null);
    if (candidate == null || _ongoingRedundant(candidate, item)) return null;
    return candidate;
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.makoloSurfaces;
    final textTheme = Theme.of(context).textTheme;
    final summary = _ongoingSummary(item.title, item.synthesis);
    final supporting = _supportingLine();
    final imageUrl = ongoingRecognitionImageUrl(item.mediaUrl, baseUri);
    final imageMime =
        item.mediaBindings
            .where(
              (binding) =>
                  binding['purpose'] == 'RECOGNIZE' &&
                  binding['resource'] is Map &&
                  (binding['resource'] as Map)['url'] == item.mediaUrl,
            )
            .map((binding) => (binding['resource'] as Map)['mime_type'])
            .whereType<String>()
            .firstOrNull ??
        'image/png';
    final whenLabel = MakoloHumanization.humanizeOwnerWhenLabel(
      item.whenLabel,
      now: DateTime.now(),
    );
    final cue = item.cue;
    final cueColor = switch (item.cueTone) {
      'action' => colors.brand,
      'attention' => MakoloColors.pulse,
      'ready' => colors.success,
      _ => Theme.of(context).colorScheme.onSurfaceVariant,
    };

    return Semantics(
      button: true,
      selected: selected,
      label: [item.title, ?summary, ?supporting].join('. '),
      child: InkWell(
        key: const Key('ongoing-n1-open-unit'),
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (cue != null || whenLabel != null) ...[
                    Wrap(
                      spacing: MakoloSpacing.sm,
                      runSpacing: MakoloSpacing.xs,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        if (cue != null)
                          DecoratedBox(
                            decoration: BoxDecoration(
                              color: cueColor.withValues(alpha: 0.09),
                              borderRadius: BorderRadius.circular(
                                MakoloRadii.pill,
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: MakoloSpacing.sm,
                                vertical: MakoloSpacing.xs,
                              ),
                              child: Text(
                                cue,
                                style: textTheme.labelSmall?.copyWith(
                                  color: cueColor,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                          ),
                        if (whenLabel != null)
                          Text(
                            whenLabel,
                            style: textTheme.labelMedium?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                  ],
                  Text(item.title, style: textTheme.titleLarge),
                  if (summary != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      summary,
                      style: textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  if (supporting != null) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      supporting,
                      style: textTheme.bodyMedium?.copyWith(
                        color: colors.brand,
                      ),
                    ),
                  ],
                  if (item.placeLabel != null) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Row(
                      children: [
                        Icon(
                          Icons.place_outlined,
                          size: 16,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: MakoloSpacing.xs),
                        Expanded(
                          child: Text(
                            item.placeLabel!,
                            style: textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                  if (stale) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      'Dernière information connue',
                      style: textTheme.bodySmall,
                    ),
                  ],
                ],
              ),
            ),
            if (imageUrl != null)
              InkWell(
                key: const Key('ongoing-n1-open-media'),
                onTap: api == null
                    ? null
                    : () => _openOngoingProtectedMedia(
                        context,
                        api: api!,
                        profileId: profileId,
                        imageUrl: imageUrl,
                        title: item.mediaAlt ?? item.title,
                        mimeType: imageMime,
                      ),
                child: AspectRatio(
                  key: const Key('ongoing-n1-full-width-media'),
                  aspectRatio: 16 / 9,
                  child: api == null
                      ? Image.network(
                          imageUrl,
                          key: const Key('ongoing-n1-recognition-media'),
                          fit: BoxFit.cover,
                          semanticLabel: item.mediaAlt ?? item.title,
                          errorBuilder: (context, error, stackTrace) =>
                              const SizedBox.shrink(),
                        )
                      : _OngoingProtectedImage(
                          key: const Key('ongoing-n1-recognition-media'),
                          api: api!,
                          profileId: profileId,
                          imageUrl: imageUrl,
                          label: item.mediaAlt ?? item.title,
                        ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _OngoingFocusPlaceholder extends StatelessWidget {
  const _OngoingFocusPlaceholder();
  @override
  Widget build(BuildContext context) => const MakoloFocusPane(
    child: Padding(
      padding: EdgeInsets.all(MakoloSpacing.lg),
      child: Text('Choisissez une démarche.'),
    ),
  );
}

class _OngoingFocus extends StatelessWidget {
  const _OngoingFocus({
    required this.profileId,
    required this.item,
    required this.onBack,
    required this.stale,
    this.api,
    this.baseUri,
  });

  final String? profileId;
  final OngoingContinuityPresentation item;
  final VoidCallback onBack;
  final bool stale;
  final MakoloApiClient? api;
  final Uri? baseUri;

  List<Widget> _detailSections(BuildContext context) {
    final seen = <String>{};
    List<String> unique(Iterable<String> values) => [
      for (final value in values)
        if (value.trim().isNotEmpty &&
            !_ongoingRedundant(value, item) &&
            seen.add(_ongoingKey(value)))
          value.trim(),
    ];

    seen
      ..add(_ongoingKey(item.title))
      ..add(_ongoingKey(item.synthesis));
    final sections = <Widget>[];

    // Human dates come from owner facts, never technical update timestamps.
    final dates = <String>[];
    for (final fact in item.temporalFacts) {
      final raw = fact['at'] ?? fact['date'];
      final parsed = MakoloHumanization.tryParseInstant(raw);
      if (parsed == null) continue;
      final label = fact['label'] is String ? fact['label'] as String : 'Date';
      final formatted = fact['at'] == null
          ? MakoloHumanization.formatDay(parsed, now: DateTime.now())
          : MakoloHumanization.formatDateTime(parsed, now: DateTime.now());
      final text = '$label · $formatted';
      if (!dates.contains(text)) dates.add(text);
    }
    if (dates.isNotEmpty) {
      sections.add(_DimensionSection(title: 'Dates à retenir', values: dates));
    }

    // Only owner-backed human descriptions are exposed, not relation IDs.
    final related = unique([
      for (final relation in item.relations)
        if ((relation['summary'] ?? relation['label']) is String)
          (relation['summary'] ?? relation['label']) as String,
    ]);
    if (related.isNotEmpty) {
      sections.add(_DimensionSection(title: 'À relier', values: related));
    }

    final result = item.outcome['summary'] ?? item.outcome['title'];
    if (result is String && result.trim().isNotEmpty) {
      final outcomes = unique([result]);
      if (outcomes.isNotEmpty) {
        sections.add(_DimensionSection(title: 'Résultat', values: outcomes));
      }
    }

    // Settled — what's already done
    final settledValues = unique(item.settled);
    if (settledValues.isNotEmpty) {
      sections.add(
        _DimensionSection(title: 'Déjà réglé', values: settledValues),
      );
    }

    // My side — explicit action from me
    final mySideValues = unique(item.mySide);
    if (mySideValues.isNotEmpty) {
      sections.add(
        _DimensionSection(
          title: 'De votre côté',
          values: mySideValues,
          emphasis: true,
        ),
      );
    }

    // Elsewhere — things moving on the other side
    final elsewhereValues = unique(item.elsewhere);
    if (elsewhereValues.isNotEmpty) {
      sections.add(
        _DimensionSection(title: 'Ailleurs', values: elsewhereValues),
      );
    }

    final prepared = unique(item.makolo);
    if (prepared.isNotEmpty) {
      sections.add(_DimensionSection(title: 'Déjà préparé', values: prepared));
    }

    final systemOrTime = unique(item.systemOrTime);
    if (systemOrTime.isNotEmpty) {
      sections.add(_DimensionSection(title: 'À venir', values: systemOrTime));
    }

    // Next — what follows
    final nextValues = unique(item.next);
    if (nextValues.isNotEmpty) {
      sections.add(_DimensionSection(title: 'Ensuite', values: nextValues));
    }

    // Waiting — hourglass row
    if (item.waiting != null) {
      final waitingText = unique([item.waiting!]);
      if (waitingText.isNotEmpty) {
        sections.add(
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.lg),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.hourglass_top_outlined,
                  size: 18,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: MakoloSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'En attente',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(waitingText.first),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      }
    }

    // Blocker — attention block with warning styling
    if (item.blocker != null) {
      final blockerText = unique([item.blocker!]);
      if (blockerText.isNotEmpty) {
        sections.add(
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.lg),
            child: MakoloAttentionBlock(
              title: 'Ce qui bloque',
              body: blockerText.first,
              icon: Icons.block_outlined,
            ),
          ),
        );
      }
    }

    // Unknown — to verify
    if (item.unknown != null) {
      final unknownText = unique([item.unknown!]);
      if (unknownText.isNotEmpty) {
        sections.add(
          _DimensionSection(title: 'À vérifier', values: unknownText),
        );
      }
    }

    return sections;
  }

  List<MakoloMetadataItem> _humanMetadata() {
    final metadata = <MakoloMetadataItem>[];
    final start = MakoloHumanization.tryParseInstant(item.timing['start_at']);
    if (start != null) {
      metadata.add(
        MakoloMetadataItem(
          MakoloHumanization.formatDateTime(start, now: DateTime.now()),
          icon: Icons.schedule_outlined,
        ),
      );
    }

    final place = [
      item.place['name'],
      item.place['locality'],
    ].whereType<String>().where((value) => value.trim().isNotEmpty).toSet();
    if (place.isNotEmpty) {
      metadata.add(
        MakoloMetadataItem(place.join(' · '), icon: Icons.place_outlined),
      );
    }
    return metadata;
  }

  Widget _mediaGallery(BuildContext context) {
    final available = <(String, String, String)>[];
    final seen = <String>{};
    for (final binding in item.mediaBindings) {
      if (binding['purpose'] != 'RECOGNIZE') continue;
      final raw = binding['resource'];
      if (raw is! Map) continue;
      final mime = raw['mime_type'];
      if (mime != 'image/jpeg' && mime != 'image/png') continue;
      final url = ongoingRecognitionImageUrl(raw['url']?.toString(), baseUri);
      if (url == null || !seen.add(url)) continue;
      available.add((
        url,
        raw['alt_text']?.toString() ?? item.title,
        mime.toString(),
      ));
    }
    if (available.isEmpty || api == null) return const SizedBox.shrink();
    return Padding(
      key: const Key('ongoing-n2-media-gallery'),
      padding: const EdgeInsets.only(top: MakoloSpacing.md),
      child: SizedBox(
        height: 220,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: available.length,
          separatorBuilder: (_, _) => const SizedBox(width: MakoloSpacing.sm),
          itemBuilder: (context, index) {
            final media = available[index];
            return ClipRRect(
              borderRadius: BorderRadius.circular(MakoloRadii.card),
              child: SizedBox(
                width: MediaQuery.sizeOf(context).width < 500 ? 290 : 350,
                child: InkWell(
                  onTap: () => _openOngoingProtectedMedia(
                    context,
                    api: api!,
                    profileId: profileId,
                    imageUrl: media.$1,
                    title: media.$2,
                    mimeType: media.$3,
                  ),
                  child: _OngoingProtectedImage(
                    api: api!,
                    profileId: profileId,
                    imageUrl: media.$1,
                    label: media.$2,
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _resources() =>
      _OngoingResourceList(item: item, baseUri: baseUri, compact: false);

  @override
  Widget build(BuildContext context) {
    final showBack =
        MediaQuery.sizeOf(context).width < MakoloLayout.ongoingSplitMinWidth;
    final metadata = _humanMetadata();
    final nativeOwnerRoute = _OngoingN1Details.routeFor(item);
    return SingleChildScrollView(
      key: ValueKey('ongoing-n2-scroll-${item.id}'),
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
      child: MakoloFocusPane(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showBack)
              TextButton.icon(
                onPressed: onBack,
                icon: const Icon(Icons.arrow_back),
                label: const Text('En cours'),
              ),
            Text(item.title, style: Theme.of(context).textTheme.headlineMedium),
            if (item.cue != null) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                item.cue!,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
            if (stale) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                'Dernière information connue',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: MakoloSpacing.xs),
            Text(item.synthesis, style: Theme.of(context).textTheme.bodyLarge),
            ..._detailSections(context),
            _mediaGallery(context),
            _resources(),
            if (nativeOwnerRoute != null) ...[
              const SizedBox(height: MakoloSpacing.xl),
              FilledButton(
                onPressed: () => context.push(nativeOwnerRoute),
                child: const Text('Ouvrir la démarche'),
              ),
            ],
            if (metadata.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: MakoloSpacing.lg),
                child: MakoloMetadata(items: metadata),
              ),
          ],
        ),
      ),
    );
  }
}

class _DimensionSection extends StatelessWidget {
  const _DimensionSection({
    required this.title,
    required this.values,
    this.emphasis = false,
  });
  final String title;
  final List<String> values;
  final bool emphasis;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: MakoloSpacing.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            color: emphasis ? Theme.of(context).colorScheme.primary : null,
          ),
        ),
        const SizedBox(height: MakoloSpacing.sm),
        for (final value in values) ...[
          Text(value, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: MakoloSpacing.xs),
        ],
      ],
    ),
  );
}
