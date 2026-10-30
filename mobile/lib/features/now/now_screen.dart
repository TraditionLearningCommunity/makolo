import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../app/sync_lifecycle.dart';
import '../../network/makolo_api_client.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/presentation_media.dart';
import '../../design/surface_states.dart';
import '../../navigation/deep_link_resolver.dart';
import '../../navigation/destination.dart';
import '../../navigation/refresh_boundary.dart';
import '../../presentation/contracts/now_presentation.dart';
export '../../presentation/contracts/now_presentation.dart'
    show NowTopology, topologyFor;
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import '../../sync/projection_contract.dart';
import '../../sync/sync_engine.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'now_selector.dart';
import 'now_media_viewer.dart';
import 'now_inline_media_preview.dart';
import 'now_action_controller.dart';
import 'now_display_labels.dart';

class NowScreen extends StatefulWidget {
  const NowScreen({
    super.key,
    required this.repository,
    this.now,
    this.api,
    this.profileId,
    this.sync,
  });

  final PersonalRepository repository;
  final SyncEngine? sync;
  final MakoloApiClient? api;
  final String? profileId;
  final DateTime Function()? now;

  @override
  State<NowScreen> createState() => _NowScreenState();

  static String? ownerPathFor(StructuredDestination destination) {
    final encoded = StructuredDestination(
      kind: destination.kind,
      id: Uri.encodeComponent(destination.id),
      link: destination.link,
    );
    final resolved = const DeepLinkResolver().resolve(encoded);
    if (resolved != null) return resolved;

    return switch (destination.kind.toLowerCase()) {
      'conversation' => '/conversations/${encoded.id}',
      _ => null,
    };
  }
}

class _NowScreenState extends State<NowScreen> {
  late Stream<StoredProjection?> _projectionStream;
  late Stream<OwnerSourceState> _sourceStream;
  DateTime? _pagedBaseReceivedAt;
  String? _pagedActorId;
  final List<Map<String, dynamic>> _pagedItems = [];
  Map<String, dynamic>? _pageContinuation;
  bool _paging = false;
  bool _pageFailed = false;

  void _resetPages() {
    _pagedBaseReceivedAt = null;
    _pagedActorId = null;
    _pagedItems.clear();
    _pageContinuation = null;
    _paging = false;
    _pageFailed = false;
  }

  void _matchBase(StoredProjection projection) {
    final actor = projection.payload['actor'];
    final actorId = actor is Map ? actor['id']?.toString() : null;
    if (_pagedBaseReceivedAt != projection.receivedAt ||
        _pagedActorId != actorId) {
      _resetPages();
      _pagedBaseReceivedAt = projection.receivedAt;
      _pagedActorId = actorId;
    }
  }

  StoredProjection _withPages(StoredProjection projection) {
    if (_pagedItems.isEmpty) return projection;
    final original = projection.payload['items'];
    final firstPage = original is List ? original : const <dynamic>[];
    final identities = <String>{};
    final merged = <dynamic>[];
    for (final item in [...firstPage, ..._pagedItems]) {
      if (item is! Map) continue;
      final identity = item['continuity_identity'] ?? item['id'];
      if (identity is String && !identities.add(identity)) continue;
      merged.add(item);
    }
    return StoredProjection(
      kind: projection.kind,
      resourceKey: projection.resourceKey,
      schemaVersion: projection.schemaVersion,
      payload: {
        ...projection.payload,
        'items': merged,
        if (_pageContinuation != null) 'continuation': _pageContinuation,
      },
      receivedAt: projection.receivedAt,
      sourceGeneratedAt: projection.sourceGeneratedAt,
      sourceUpdatedAt: projection.sourceUpdatedAt,
      lastVerifiedOnlineAt: projection.lastVerifiedOnlineAt,
      freshUntil: projection.freshUntil,
      expiresAt: projection.expiresAt,
      freshnessPolicyId: projection.freshnessPolicyId,
    );
  }

  Future<void> _loadMore(StoredProjection base) async {
    if (_paging || _pageFailed || widget.api == null || !mounted) return;
    _matchBase(base);
    final rawContinuation = _pageContinuation ?? base.payload['continuation'];
    if (rawContinuation is! Map || rawContinuation['state'] != 'more') {
      return;
    }
    final token = rawContinuation['token'];
    if (token is! String || token.isEmpty) return;
    final baseReceivedAt = base.receivedAt;
    final actorId = _pagedActorId;
    setState(() => _paging = true);
    try {
      final query = Uri(queryParameters: {'continuation': token}).query;
      final response = await widget.api!.get('api/v1/me/now/?$query');
      final envelope = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.now',
        expectedScope: 'personal',
      );
      final data = envelope.data;
      final actor = data['actor'];
      final items = data['items'];
      final next = data['continuation'];
      if (actor is! Map ||
          actor['id'] != actorId ||
          items is! List ||
          next is! Map ||
          !const ['more', 'end'].contains(next['state']) ||
          (next['state'] == 'more' &&
              (items.isEmpty || next['token'] == token))) {
        throw const FormatException('Invalid Now continuation page');
      }
      if (!mounted ||
          _pagedBaseReceivedAt != baseReceivedAt ||
          _pagedActorId != actorId) {
        return;
      }
      setState(() {
        _pagedItems.addAll(
          items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)),
        );
        _pageContinuation = Map<String, dynamic>.from(next);
        _pageFailed = false;
      });
    } on Object {
      if (mounted &&
          _pagedBaseReceivedAt == baseReceivedAt &&
          _pagedActorId == actorId) {
        setState(() => _pageFailed = true);
      }
    } finally {
      if (mounted && _pagedBaseReceivedAt == baseReceivedAt) {
        setState(() => _paging = false);
      }
    }
  }

  @override
  void initState() {
    super.initState();
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant NowScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.profileId != widget.profileId) {
      _resetPages();
      _bindStreams();
    }
  }

  void _bindStreams() {
    _projectionStream = widget.repository.watchNow();
    _sourceStream = widget.repository.watchNowSource();
  }

  @override
  Widget build(BuildContext context) {
    return MakoloRefreshBoundary(
      child: StreamBuilder<OwnerSourceState>(
        stream: _sourceStream,
        initialData: OwnerSourceState.unknown,
        builder: (context, sourceSnapshot) {
          final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
          return StreamBuilder<StoredProjection?>(
            stream: _projectionStream,
            builder: (context, projectionSnapshot) {
              return _buildProjection(context, projectionSnapshot, source);
            },
          );
        },
      ),
    );
  }

  Widget _buildProjection(
    BuildContext context,
    AsyncSnapshot<StoredProjection?> snapshot,
    OwnerSourceState source,
  ) {
    final syncStatus = SyncStatusScope.maybeOf(context);
    final projection = snapshot.data;

    if (projection == null) {
      if (snapshot.hasError ||
          source.lastErrorCode != null ||
          syncStatus?.state == SyncVisualState.failed) {
        return MakoloErrorState(
          message: 'Now indisponible.',
          preservedMessage: '',
          onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
        );
      }
      final loading =
          snapshot.connectionState == ConnectionState.waiting ||
          syncStatus?.state == SyncVisualState.syncing;
      if (loading) {
        return const MakoloSurfaceStateView(
          state: MakoloSurfacePresentation(
            availability: MakoloAvailabilityCue.loading,
          ),
          content: SizedBox.shrink(),
        );
      }

      return const MakoloEmptyState(
        title: 'Now indisponible.',
        icon: Icons.adjust,
      );
    }

    _matchBase(projection);
    final selection = const NowSelector().select(
      projection: _withPages(projection),
      now: (widget.now?.call() ?? DateTime.now()).toUtc(),
      reachability: _reachability(source, syncStatus),
      failure:
          source.lastErrorCode != null ||
              syncStatus?.state == SyncVisualState.failed
          ? MakoloFailureCue.recoverable
          : MakoloFailureCue.none,
      refreshing: syncStatus?.state == SyncVisualState.syncing,
      sourceInvalidated:
          source.invalidated || syncStatus?.state == SyncVisualState.stale,
    );

    final view = NowView(
      selection: selection,
      api: widget.api,
      profileId: widget.profileId,
      // The shell already signals connectivity; do not repeat it above
      // previously available Now content.
      refreshErrorMessage: null,
      onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
      onOpenOwner: (destination) => _openOwner(context, destination),
      onLoadMore: () => _loadMore(projection),
      loadingMore: _paging,
      loadMoreFailed: _pageFailed,
      onRetryMore: () {
        setState(() => _pageFailed = false);
        _loadMore(projection);
      },
    );
    final sync = widget.sync;
    return sync == null
        ? view
        : NowActionRefreshScope(
            onRefresh: () => sync.pull(SyncEngine.roots.first),
            child: view,
          );
  }

  MakoloReachabilityCue _reachability(
    OwnerSourceState source,
    SyncStatus? syncStatus,
  ) {
    if (syncStatus?.state == SyncVisualState.offline) {
      return MakoloReachabilityCue.temporarilyUnavailable;
    }

    return switch (source.reachability) {
      ReachabilityState.unknown => MakoloReachabilityCue.unknown,
      ReachabilityState.reachable => MakoloReachabilityCue.reachable,
      ReachabilityState.unreachable =>
        MakoloReachabilityCue.temporarilyUnavailable,
    };
  }

  void _openOwner(BuildContext context, StructuredDestination destination) {
    final path = NowScreen.ownerPathFor(destination);
    if (path != null) context.push(path);
  }
}

class NowView extends StatefulWidget {
  const NowView({
    super.key,
    required this.selection,
    this.onOpenOwner,
    this.api,
    this.initialSelectedKey,
    this.profileId,
    this.refreshErrorMessage,
    this.onRetry,
    this.onLoadMore,
    this.onRetryMore,
    this.loadingMore = false,
    this.loadMoreFailed = false,
  });

  final NowSelection selection;
  final VoidCallback? onLoadMore;
  final VoidCallback? onRetryMore;
  final bool loadingMore;
  final bool loadMoreFailed;
  final String? refreshErrorMessage;
  final VoidCallback? onRetry;
  final String? initialSelectedKey;
  final String? profileId;
  final MakoloApiClient? api;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  State<NowView> createState() => _NowViewState();
}

class _NowViewState extends State<NowView> {
  final ScrollController _fieldController = ScrollController();
  String? _selectedKey;

  @override
  void initState() {
    super.initState();
    _selectedKey = widget.initialSelectedKey;
    _fieldController.addListener(_maybeLoadMore);
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeLoadMore());
  }

  void _maybeLoadMore() {
    if (!mounted ||
        !_fieldController.hasClients ||
        widget.loadingMore ||
        widget.loadMoreFailed ||
        widget.selection.continuation.state != NowContinuationState.more) {
      return;
    }
    if (_fieldController.position.extentAfter < 480) {
      widget.onLoadMore?.call();
    }
  }

  @override
  void didUpdateWidget(covariant NowView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.selection.situations.length !=
            widget.selection.situations.length ||
        oldWidget.loadingMore != widget.loadingMore ||
        oldWidget.loadMoreFailed != widget.loadMoreFailed) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeLoadMore());
    }
    if (_selectedKey != null &&
        !_situations.any((item) => _keyOf(item) == _selectedKey)) {
      _selectedKey = null;
    }
  }

  @override
  void dispose() {
    _fieldController.dispose();
    super.dispose();
  }

  List<NowSituationPresentation> get _situations => widget.selection.situations;

  NowSituationPresentation? get _selected {
    final key = _selectedKey;
    if (key == null) return null;
    for (final item in _situations) {
      if (_keyOf(item) == key) return item;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selected;
    final field = _NowField(
      situations: _situations,
      controller: _fieldController,
      selectedKey: _selectedKey,
      onSelect: _select,
      onOpenOwner: widget.onOpenOwner,
      api: widget.api,
      profileId: widget.profileId,
      loadingMore: widget.loadingMore,
      loadMoreFailed: widget.loadMoreFailed,
      onRetryMore: widget.onRetryMore,
    );

    final content = selected == null
        ? LayoutBuilder(
            builder: (context, constraints) {
              // Discover-style full width on phones; calm reading width on
              // tablets and desktop, without a double mobile outer gutter.
              if (constraints.maxWidth < MakoloLayout.mediumMinWidth) {
                return field;
              }
              return MakoloContentFrame(
                maxContentWidth: MakoloLayout.calmMaxWidth,
                child: field,
              );
            },
          )
        : MakoloAdaptiveSplit(
            splitAt: MakoloLayout.nowFocusSplitMinWidth,
            field: MakoloContentFrame(child: field),
            focus: MakoloContentFrame(
              child: _NowDepth(
                situation: selected,
                onClose: _closeDepth,
                onOpenOwner: widget.onOpenOwner,
                api: widget.api,

                profileId: widget.profileId,
              ),
            ),
            narrow: MakoloContentFrame(
              maxContentWidth: MakoloLayout.calmMaxWidth,
              child: _NowDepth(
                situation: selected,
                onClose: _closeDepth,
                onOpenOwner: widget.onOpenOwner,
                api: widget.api,

                profileId: widget.profileId,
              ),
            ),
          );

    final state = widget.selection.state;
    final surface = MakoloSurfaceStateView(
      state: state,
      recoverableErrorMessage: widget.refreshErrorMessage,
      preservedMessage: '',
      onRetry: widget.onRetry,
      empty: widget.selection.isCalm
          ? const _NowCalm()
          : const _NowUnavailable(),
      content: content,
    );
    final cues = <Widget>[
      if (state.refreshing)
        Semantics(
          label: 'Actualisation en cours',
          child: const LinearProgressIndicator(minHeight: 2),
        ),
      if (state.freshness != MakoloFreshnessCue.unknown &&
          state.freshness != MakoloFreshnessCue.current)
        MakoloFreshnessNotice(freshness: state.freshness),
    ];

    return PopScope<Object?>(
      canPop: _selected == null,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && _selected != null) _closeDepth();
      },
      child: cues.isEmpty
          ? surface
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final cue in cues)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      MakoloSpacing.md,
                      MakoloSpacing.sm,
                      MakoloSpacing.md,
                      0,
                    ),
                    child: cue,
                  ),
                Expanded(child: surface),
              ],
            ),
    );
  }

  void _select(NowSituationPresentation situation) {
    setState(() => _selectedKey = _keyOf(situation));
  }

  void _closeDepth() {
    if (_selectedKey == null) return;
    setState(() => _selectedKey = null);
  }

  String _keyOf(NowSituationPresentation situation) => situation.identity;
}

class _NowField extends StatelessWidget {
  const _NowField({
    required this.situations,
    required this.controller,
    required this.selectedKey,
    required this.onSelect,
    required this.onOpenOwner,
    required this.api,
    required this.profileId,
    required this.loadingMore,
    required this.loadMoreFailed,
    required this.onRetryMore,
  });

  final bool loadingMore;
  final bool loadMoreFailed;
  final VoidCallback? onRetryMore;
  final List<NowSituationPresentation> situations;
  final ScrollController controller;
  final String? selectedKey;
  final ValueChanged<NowSituationPresentation> onSelect;
  final ValueChanged<StructuredDestination>? onOpenOwner;
  final MakoloApiClient? api;
  final String? profileId;

  @override
  Widget build(BuildContext context) {
    if (situations.isEmpty) return const _NowCalm();

    final primary = situations.first;
    final secondary = situations.skip(1).toList(growable: false);
    final theme = Theme.of(context);

    return ListView(
      // A distinct gutter (rather than a line alone) separates Now units.
      key: const PageStorageKey<String>('now-field-scroll'),
      controller: controller,
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(
        top: MakoloSpacing.sm,
        bottom: MakoloSpacing.xl,
      ),
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
          child: _NowSituationUnit(
            situation: primary,
            selected: selectedKey == _keyOf(primary),
            onSelect: () => onSelect(primary),
            onOpenOwner: onOpenOwner,
            api: api,
            profileId: profileId,
          ),
        ),
        if (secondary.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.md,
              MakoloSpacing.lg,
              MakoloSpacing.md,
              MakoloSpacing.sm,
            ),
            child: Text('Aussi maintenant', style: theme.textTheme.titleMedium),
          ),
          for (final item in secondary)
            Padding(
              key: ValueKey('now-unit-${item.identity}'),
              padding: const EdgeInsets.only(top: MakoloSpacing.md),
              child: _NowSituationUnit(
                situation: item,
                selected: selectedKey == _keyOf(item),
                onSelect: () => onSelect(item),
                onOpenOwner: onOpenOwner,
                api: api,
                profileId: profileId,
              ),
            ),
        ],
        if (loadingMore)
          const Padding(
            padding: EdgeInsets.all(MakoloSpacing.lg),
            child: Center(child: CircularProgressIndicator.adaptive()),
          )
        else if (loadMoreFailed)
          Center(
            child: TextButton.icon(
              onPressed: onRetryMore,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Réessayer'),
            ),
          ),
      ],
    );
  }

  String _keyOf(NowSituationPresentation situation) => situation.identity;
}

String _presentationKey(String value) => value
    .trim()
    .toLowerCase()
    .replaceAll(RegExp(r'\s+'), ' ')
    .replaceAll(RegExp(r'[.:;–—-]+$'), '')
    .trim();

bool _samePresentationText(String? left, String? right) {
  if (left == null || right == null) return false;
  return _presentationKey(left) == _presentationKey(right);
}

String? _distinctPresentationText(String? value, Iterable<String?> others) {
  final text = value?.trim();
  if (text == null || text.isEmpty) return null;
  for (final other in others) {
    if (_samePresentationText(text, other)) return null;
  }
  return text;
}

class _NowSemanticContent extends StatelessWidget {
  const _NowSemanticContent({
    required this.situation,
    required this.api,
    required this.profileId,
    required this.onOpenOwner,
    this.compact = false,
  });

  final NowSituationPresentation situation;
  final MakoloApiClient? api;
  final String? profileId;
  final ValueChanged<StructuredDestination>? onOpenOwner;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final topology = topologyFor(situation);
    final theme = Theme.of(context);
    // Never promote a media reference to the lead visual unless the
    // authenticated reader can actually open it on this device.
    final readable = situation.mediaBindings
        .where(
          (media) =>
              media.canRender &&
              api != null &&
              nowAuthorizedMediaPath(media) != null,
        )
        .toList(growable: false);
    NowMediaBindingPresentation? dominantMedia;
    for (final media in readable) {
      if (media.canDominate) {
        dominantMedia = media;
        break;
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (dominantMedia != null) ...[
          const SizedBox(height: MakoloSpacing.md),
          Semantics(
            button:
                api != null && nowAuthorizedMediaPath(dominantMedia) != null,
            label: dominantMedia.label ?? 'Lire le média dans Makolo',
            child: InkWell(
              onTap:
                  api != null && nowAuthorizedMediaPath(dominantMedia) != null
                  ? () => _openMedia(context, dominantMedia!)
                  : null,
              child: MakoloMediaFrame(
                aspect: switch (dominantMedia.kind) {
                  NowMediaKind.pdf => MakoloMediaAspect.document,
                  NowMediaKind.video => MakoloMediaAspect.landscape,
                  _ => MakoloMediaAspect.standard,
                },
                semanticLabel:
                    dominantMedia.label ?? 'Média lié à la situation',
                placeholder: MakoloMediaPlaceholder(
                  icon: _mediaIcon(dominantMedia.kind),
                  label: dominantMedia.label ?? 'Média associé',
                ),
                child:
                    dominantMedia.kind == NowMediaKind.image &&
                        api != null &&
                        profileId != null &&
                        nowAuthorizedMediaPath(dominantMedia) != null
                    ? NowInlineMediaPreview(
                        key: ValueKey(dominantMedia.resourceRef),
                        media: dominantMedia,
                        api: api!,
                        profileId: profileId!,
                        placeholder: MakoloMediaPlaceholder(
                          icon: _mediaIcon(dominantMedia.kind),
                          label: dominantMedia.label ?? 'Média associé',
                        ),
                      )
                    : null,
              ),
            ),
          ),
        ],
        if (topology == NowTopology.composition) ...[
          if (!compact)
            for (final relation in situation.relations)
              if (_distinctPresentationText(relation.summary, [
                    situation.meaning,
                    situation.whyNow,
                    situation.consequence,
                  ])
                  case final summary?)
                Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                  child: Text(summary, style: theme.textTheme.bodyMedium),
                ),
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Wrap(
              spacing: MakoloSpacing.sm,
              runSpacing: MakoloSpacing.xs,
              children: [
                for (final member in situation.relationMembers)
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(member.label),
                  ),
              ],
            ),
          ),
        ],
        if (situation.knowledgeState case final knowledge?)
          if (knowledge != 'known' && knowledge != 'fresh')
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.sm),
              child: Text(
                'Information à vérifier',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
        if (compact && situation.makoloPreparation.isNotEmpty)
          for (final prepared in situation.makoloPreparation)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(prepared, style: theme.textTheme.bodyMedium),
            ),
        if (topology == NowTopology.waiting && situation.exitCondition != null)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Text(
              situation.exitCondition!,
              style: theme.textTheme.bodyMedium,
            ),
          ),
        if (topology == NowTopology.waiting)
          Row(
            children: [
              const Icon(Icons.hourglass_top_outlined),
              const SizedBox(width: MakoloSpacing.md),
              Expanded(
                child: Text(
                  situation.turnLabel ?? 'En attente d’une évolution.',
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
          ),
        if (situation.businessActions.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.md),
          NowActionGroup(
            key: ValueKey('now-actions-${situation.identity}'),
            situation: situation,
            compact: compact,
            api: api,
            onOpenOwner:
                situation.ownerDestination != null &&
                    onOpenOwner != null &&
                    NowScreen.ownerPathFor(situation.ownerDestination!) != null
                ? () => onOpenOwner!(situation.ownerDestination!)
                : null,
          ),
        ],
        for (final media in readable)
          if (media != dominantMedia)
            TextButton.icon(
              onPressed: () => _openMedia(context, media),
              icon: Icon(_mediaIcon(media.kind)),
              label: Text(media.label ?? 'Lire le média dans Makolo'),
            ),
        if (dominantMedia != null && readable.contains(dominantMedia))
          TextButton.icon(
            onPressed: () => _openMedia(context, dominantMedia!),
            icon: const Icon(Icons.open_in_full_outlined),
            label: const Text('Lire dans Makolo'),
          ),
      ],
    );
  }

  IconData _mediaIcon(NowMediaKind kind) => switch (kind) {
    NowMediaKind.image => Icons.image_outlined,
    NowMediaKind.pdf => Icons.picture_as_pdf_outlined,
    NowMediaKind.document => Icons.description_outlined,
    NowMediaKind.video => Icons.play_circle_outline,
    NowMediaKind.audio => Icons.audiotrack_outlined,
    NowMediaKind.coordinates => Icons.place_outlined,
    _ => Icons.insert_drive_file_outlined,
  };

  void _openMedia(BuildContext context, NowMediaBindingPresentation media) {
    final client = api;
    if (client == null || nowAuthorizedMediaPath(media) == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) =>
            NowMediaViewer(media: media, api: client, profileId: profileId),
      ),
    );
  }
}

/// The same edge-to-edge, subtly separated N1 geometry as Discover.
/// Situations remain owner-backed next steps, never arbitrary feed posts.
class _NowSituationUnit extends StatelessWidget {
  const _NowSituationUnit({
    required this.situation,
    required this.selected,
    required this.onSelect,
    required this.onOpenOwner,
    required this.api,
    required this.profileId,
  });

  final NowSituationPresentation situation;
  final bool selected;
  final VoidCallback onSelect;
  final ValueChanged<StructuredDestination>? onOpenOwner;
  final MakoloApiClient? api;
  final String? profileId;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    final headline = nowDisplayHeadline(
      situation.meaning,
      situation.humanContext,
    );
    final title = contextLabel ?? headline;
    final description = contextLabel == null
        ? null
        : _distinctPresentationText(headline, [title]);
    final subject = _distinctPresentationText(situation.subject, [
      title,
      headline,
      situation.humanContext,
    ]);
    final whyNow = _distinctPresentationText(situation.whyNow, [
      situation.meaning,
      situation.humanContext,
      headline,
    ]);
    final consequence = _distinctPresentationText(situation.consequence, [
      situation.meaning,
      situation.humanContext,
      headline,
      situation.whyNow,
    ]);
    final delta = _distinctPresentationText(situation.delta, [
      title,
      headline,
      situation.whyNow,
    ]);
    final owner = situation.ownerDestination;
    final canOpenOwner =
        owner != null &&
        onOpenOwner != null &&
        NowScreen.ownerPathFor(owner) != null &&
        situation.responseLabel != null &&
        situation.businessActions.isEmpty;

    return Semantics(
      container: true,
      explicitChildNodes: true,
      label: [title, ?description, ?consequence, ?whyNow].join('. '),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: selected
              ? theme.colorScheme.primary.withValues(alpha: 0.04)
              : theme.colorScheme.surface,
          border: Border(
            bottom: BorderSide(color: theme.colorScheme.outlineVariant),
          ),
        ),
        child: InkWell(
          onTap: onSelect,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.md,
              vertical: MakoloSpacing.compact,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(title, style: theme.textTheme.titleLarge),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Icon(
                      Icons.chevron_right_rounded,
                      size: 20,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ],
                ),
                if (situation.topology == NowTopology.media)
                  _NowSemanticContent(
                    situation: situation,
                    compact: true,
                    api: api,
                    profileId: profileId,
                    onOpenOwner: onOpenOwner,
                  ),
                if (subject != null) ...[
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    subject,
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                if (description != null) ...[
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(description, style: theme.textTheme.bodyMedium),
                ],
                if (delta != null) ...[
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    delta,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
                if (consequence != null) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  Text(
                    consequence,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.primary,
                    ),
                  ),
                ],
                if (whyNow != null) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  Text(
                    whyNow,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                if (situation.topology != NowTopology.media)
                  _NowSemanticContent(
                    situation: situation,
                    compact: true,
                    api: api,
                    profileId: profileId,
                    onOpenOwner: onOpenOwner,
                  ),
                if (situation.metadata.isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  MakoloMetadata(
                    items: [
                      for (final item in situation.metadata)
                        MakoloMetadataItem(item),
                    ],
                  ),
                ],
                if (canOpenOwner) ...[
                  const SizedBox(height: MakoloSpacing.xs),
                  TextButton.icon(
                    onPressed: () => onOpenOwner!(owner),
                    icon: const Icon(Icons.arrow_forward_rounded),
                    label: Text(
                      nowDisplayHandoffLabel(
                        situation.responseLabel!,
                        situation.meaning,
                        situation.humanContext,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NowDepth extends StatelessWidget {
  const _NowDepth({
    required this.situation,
    required this.onClose,
    required this.onOpenOwner,
    required this.api,
    required this.profileId,
  });

  final NowSituationPresentation situation;
  final VoidCallback onClose;
  final ValueChanged<StructuredDestination>? onOpenOwner;
  final MakoloApiClient? api;
  final String? profileId;

  Widget _section(String title, String content) => Padding(
    padding: const EdgeInsets.only(top: MakoloSpacing.lg),
    child: MakoloSection(
      title: title,
      padding: EdgeInsets.zero,
      child: Text(content),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final topology = topologyFor(situation);
    final ownerDestination = situation.ownerDestination;
    final canOpenOwner =
        ownerDestination != null &&
        NowScreen.ownerPathFor(ownerDestination) != null &&
        situation.responseLabel != null &&
        onOpenOwner != null &&
        situation.businessActions.isEmpty;
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    final whyNow = _distinctPresentationText(situation.whyNow, [
      situation.meaning,
      situation.humanContext,
    ]);
    final consequence = _distinctPresentationText(situation.consequence, [
      situation.meaning,
      situation.whyNow,
    ]);
    final delta = _distinctPresentationText(situation.delta, [
      situation.meaning,
      situation.humanContext,
      situation.whyNow,
    ]);
    final subject = _distinctPresentationText(situation.subject, [
      situation.humanContext,
      situation.meaning,
    ]);
    final firstVisual =
        topology == NowTopology.media ||
        topology == NowTopology.waiting ||
        topology == NowTopology.composition;
    final detail = _NowSemanticContent(
      situation: situation,
      api: api,
      profileId: profileId,
      onOpenOwner: onOpenOwner,
    );

    return SingleChildScrollView(
      key: ValueKey('now-n2-scroll-${situation.identity}'),
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      child: MakoloFocusPane(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                onPressed: onClose,
                icon: const Icon(Icons.arrow_back_rounded),
                label: const Text('Maintenant'),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            if (contextLabel != null) ...[
              Text(
                contextLabel,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
            ],
            Text(
              nowDisplayHeadline(situation.meaning, situation.humanContext),
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (subject != null) _section('Sujet', subject),
            if (delta != null) _section('Ce qui a changé', delta),
            // S2, S4 and S5 lead with their evidence, waiting state or
            // relation. S1 and S3 lead with meaning and consequences.
            if (firstVisual) ...[
              const SizedBox(height: MakoloSpacing.md),
              detail,
            ],
            if (consequence != null) _section('Ce que ça change', consequence),
            if (whyNow != null) _section('Pourquoi maintenant', whyNow),
            if (!firstVisual) ...[
              const SizedBox(height: MakoloSpacing.md),
              detail,
            ],
            if (topology == NowTopology.waiting &&
                situation.horizon != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Text(
                situation.horizon!,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            if (situation.makoloPreparation.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Déjà préparé',
                padding: EdgeInsets.zero,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final item in situation.makoloPreparation) Text(item),
                  ],
                ),
              ),
            ],
            if (situation.metadata.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloMetadata(
                items: [
                  for (final item in situation.metadata)
                    MakoloMetadataItem(item),
                ],
              ),
            ],
            if (canOpenOwner) ...[
              const SizedBox(height: MakoloSpacing.xl),
              FilledButton(
                onPressed: () => onOpenOwner!(ownerDestination),
                child: Text(
                  nowDisplayHandoffLabel(
                    situation.responseLabel!,
                    situation.meaning,
                    situation.humanContext,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _NowUnavailable extends StatelessWidget {
  const _NowUnavailable();

  @override
  Widget build(BuildContext context) {
    return const MakoloContentFrame(
      child: Center(
        child: Padding(
          padding: EdgeInsets.all(MakoloSpacing.inner),
          child: Text('Now n’est pas disponible pour le moment.'),
        ),
      ),
    );
  }
}

class _NowCalm extends StatelessWidget {
  const _NowCalm();

  @override
  Widget build(BuildContext context) {
    return MakoloContentFrame(
      maxContentWidth: MakoloLayout.calmMaxWidth,
      child: ListView(
        padding: const EdgeInsets.symmetric(
          vertical: MakoloSpacing.exceptional,
        ),
        children: [
          Text(
            'Tout est en ordre. ✓',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
        ],
      ),
    );
  }
}
