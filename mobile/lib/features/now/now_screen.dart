import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
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
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'now_selector.dart';
import 'now_media_viewer.dart';

class NowScreen extends StatefulWidget {
  const NowScreen({
    super.key,
    required this.repository,
    this.now,
    this.api,
    this.profileId,
  });

  final PersonalRepository repository;
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

  @override
  void initState() {
    super.initState();
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant NowScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
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
        title: 'Now n’est pas disponible pour le moment.',
        icon: Icons.adjust,
      );
    }

    final selection = const NowSelector().select(
      projection: projection,
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

    return NowView(
      selection: selection,
      api: widget.api,
      profileId: widget.profileId,
      onOpenOwner: (destination) => _openOwner(context, destination),
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
  });

  final NowSelection selection;
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
  }

  @override
  void didUpdateWidget(covariant NowView oldWidget) {
    super.didUpdateWidget(oldWidget);
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
    );

    final content = selected == null
        ? MakoloContentFrame(
            maxContentWidth: MakoloLayout.calmMaxWidth,
            child: field,
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
      empty: widget.selection.isCalm
          ? const _NowCalm()
          : const _NowUnavailable(),
      content: content,
    );
    final cues = <Widget>[
      if (state.refreshing) const MakoloRefreshIndicator(),
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
  });

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

    return ListView(
      key: const PageStorageKey<String>('now-field-scroll'),
      controller: controller,
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      children: [
        _NowPrimarySituation(
          situation: primary,
          selected: selectedKey == _keyOf(primary),
          onSelect: () => onSelect(primary),
          onOpenOwner: onOpenOwner,
          api: api,
          profileId: profileId,
        ),
        if (secondary.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.strong),
          Text(
            'Aussi maintenant',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: MakoloSpacing.md),
          for (var index = 0; index < secondary.length; index++) ...[
            _NowSecondarySituation(
              situation: secondary[index],
              onSelect: () => onSelect(secondary[index]),
            ),
            if (index != secondary.length - 1)
              const SizedBox(height: MakoloSpacing.md),
          ],
        ],
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

enum NowTopology { meaning, media, action, waiting, composition }

NowTopology topologyFor(NowSituationPresentation situation) {
  if (situation.mediaBindings.any((media) => media.canDominate)) {
    return NowTopology.media;
  }
  if (situation.businessActions.any((action) => action.canDominate)) {
    return NowTopology.action;
  }
  // A relation alone is not a composed Now situation: require a present
  // consequence and an explicit explanation from the owning projection.
  if (situation.relationMembers.length >= 2 &&
      situation.relations.isNotEmpty &&
      situation.whyNow != null &&
      situation.consequence != null &&
      situation.responseType != null) {
    return NowTopology.composition;
  }
  // Waiting is a response owned by the projection, not an inferred status.
  final response = situation.responseType?.toLowerCase();
  if (response == 'wait' || response == 'monitor' || response == 'waiting') {
    return NowTopology.waiting;
  }
  return NowTopology.meaning;
}

class _NowSemanticContent extends StatelessWidget {
  const _NowSemanticContent({
    required this.situation,
    required this.api,
    required this.profileId,
  });

  final NowSituationPresentation situation;
  final MakoloApiClient? api;
  final String? profileId;

  @override
  Widget build(BuildContext context) {
    final topology = topologyFor(situation);
    final theme = Theme.of(context);
    final dominantMedia = topology == NowTopology.media
        ? situation.mediaBindings.firstWhere((media) => media.canDominate)
        : null;
    final readable = situation.mediaBindings
        .where(
          (media) =>
              media.canRender &&
              api != null &&
              nowAuthorizedMediaPath(media) != null,
        )
        .toList(growable: false);

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
                  ? () => _openMedia(context, dominantMedia)
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
              ),
            ),
          ),
        ],
        if (topology == NowTopology.composition) ...[
          for (final relation in situation.relations)
            if (relation.summary != null)
              Text(relation.summary!, style: theme.textTheme.titleMedium),
          for (final member in situation.relationMembers)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.account_tree_outlined),
              title: Text(member.label),
              subtitle: member.subtext == null ? null : Text(member.subtext!),
            ),
        ],
        if (topology == NowTopology.waiting)
          Row(
            children: [
              const Icon(Icons.hourglass_top_outlined),
              const SizedBox(width: MakoloSpacing.md),
              Expanded(
                child: Text(
                  situation.turnLabel ?? 'En attente de la prochaine réponse.',
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
          ),
        if (topology == NowTopology.action)
          Text(
            situation.businessActions
                .firstWhere((action) => action.canDominate)
                .label,
            style: theme.textTheme.titleMedium,
          ),
        for (final media in readable)
          if (media != dominantMedia)
            TextButton.icon(
              onPressed: () => _openMedia(context, media),
              icon: Icon(_mediaIcon(media.kind)),
              label: Text(media.label ?? 'Lire le média dans Makolo'),
            ),
        if (dominantMedia != null && readable.contains(dominantMedia))
          TextButton.icon(
            onPressed: () => _openMedia(context, dominantMedia),
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

class _NowPrimarySituation extends StatelessWidget {
  const _NowPrimarySituation({
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
    final ownerDestination = situation.ownerDestination;
    final ownerPath = ownerDestination == null
        ? null
        : NowScreen.ownerPathFor(ownerDestination);
    final canOpenOwner =
        situation.responseLabel != null &&
        ownerPath != null &&
        onOpenOwner != null;
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    final whyNow = _distinctPresentationText(situation.whyNow, [
      situation.meaning,
      situation.humanContext,
    ]);
    return Semantics(
      container: true,
      button: true,
      selected: selected,
      label: [?contextLabel, situation.meaning, ?whyNow].join('. '),
      child: InkWell(
        onTap: onSelect,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.compact),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
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
                situation.meaning,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              if (whyNow != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  whyNow,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              _NowSemanticContent(
                situation: situation,
                api: api,
                profileId: profileId,
              ),
              if (situation.metadata.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.md),
                MakoloMetadata(
                  items: [
                    for (final item in situation.metadata)
                      MakoloMetadataItem(item),
                  ],
                ),
              ],
              if (canOpenOwner) ...[
                const SizedBox(height: MakoloSpacing.lg),
                FilledButton(
                  onPressed: () => onOpenOwner!(ownerDestination!),
                  child: Text(situation.responseLabel ?? 'Ouvrir'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _NowSecondarySituation extends StatelessWidget {
  const _NowSecondarySituation({
    required this.situation,
    required this.onSelect,
  });

  final NowSituationPresentation situation;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) {
    final contextLabel = _distinctPresentationText(situation.humanContext, [
      situation.meaning,
    ]);
    return MakoloCard(
      onTap: onSelect,
      semanticLabel: [
        ?contextLabel,
        situation.meaning,
        'Ouvrir le détail',
      ].join('. '),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (contextLabel != null) ...[
            Text(contextLabel, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: MakoloSpacing.sm),
          ],
          Text(
            situation.meaning,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (situation.metadata.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            MakoloMetadata(
              items: [
                for (final item in situation.metadata) MakoloMetadataItem(item),
              ],
            ),
          ],
        ],
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

  @override
  Widget build(BuildContext context) {
    final ownerDestination = situation.ownerDestination;
    final canOpenOwner =
        ownerDestination != null &&
        NowScreen.ownerPathFor(ownerDestination) != null &&
        situation.responseLabel != null &&
        onOpenOwner != null;
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

    return SingleChildScrollView(
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
                label: const Text('Now'),
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
              situation.meaning,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            if (whyNow != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Pourquoi maintenant',
                padding: EdgeInsets.zero,
                child: Text(whyNow),
              ),
            ],
            if (consequence != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Conséquence',
                padding: EdgeInsets.zero,
                child: Text(consequence),
              ),
            ],
            _NowSemanticContent(
              situation: situation,
              api: api,
              profileId: profileId,
            ),
            if (situation.horizon != null &&
                topologyFor(situation) == NowTopology.waiting) ...[
              const SizedBox(height: MakoloSpacing.md),
              Text(situation.horizon!),
            ],
            if (situation.makoloPreparation.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Préparé par Makolo',
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
              OutlinedButton(
                onPressed: () => onOpenOwner!(ownerDestination),
                child: Text(situation.responseLabel ?? 'Ouvrir la démarche'),
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
