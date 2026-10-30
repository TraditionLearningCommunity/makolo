import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../network/makolo_api_client.dart';
import '../../presentation/possibilities/discovery_save_icon.dart';
import '../../navigation/refresh_boundary.dart';
import '../../navigation/profile_avatar_image.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'me_selector.dart';

class MeScreen extends StatefulWidget {
  const MeScreen({
    super.key,
    required this.repository,
    this.api,
    this.now,
    this.onOpenDestination,
  });

  final PersonalRepository repository;
  final MakoloApiClient? api;
  final DateTime Function()? now;
  final bool Function(StructuredDestination destination)? onOpenDestination;

  @override
  State<MeScreen> createState() => _MeScreenState();
}

class _MeScreenState extends State<MeScreen> {
  late Stream<StoredProjection?> _projectionStream;
  late Stream<OwnerSourceState> _sourceStream;
  StoredProjection? _last;
  String? _loading;
  bool _pageFailed = false;
  bool _retryRequested = false;

  @override
  void initState() {
    super.initState();
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant MeScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _last = null;
      _loading = null;
      _pageFailed = false;
      _bindStreams();
    }
  }

  void _bindStreams() {
    _projectionStream = widget.repository.watchMe();
    _sourceStream = widget.repository.watchMeSource();
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
      return _MeFirstAvailability(
        loading: loading,
        offline: syncStatus?.state == SyncVisualState.offline,
        unavailable: source.invalidated || source.lastErrorCode != null,
      );
    }

    _last = projection;
    final selection = const MeSelector().select(
      projection: projection,
      now: (widget.now?.call() ?? DateTime.now()).toUtc(),
      reachability: _reachability(source, syncStatus),
      failure: source.lastErrorCode != null
          ? MakoloFailureCue.recoverable
          : MakoloFailureCue.none,
      refreshing: syncStatus?.state == SyncVisualState.syncing,
      sourceInvalidated: source.invalidated,
    );

    return MeView(
      selection: selection,
      mediaApi: widget.api,
      avatarProfileId: widget.repository.store.profileId,
      avatarRevision: projection.receivedAt,
      onOpenDestination: widget.onOpenDestination,
      loadingMore: _loading != null,
      loadFailed: _pageFailed,
      onRetry: () {
        setState(() {
          _pageFailed = false;
          _retryRequested = true;
        });
        _loadNext(selection);
      },
      onReachEnd:
          widget.api == null || syncStatus?.state == SyncVisualState.offline
          ? null
          : () => _loadNext(selection),
    );
  }

  Future<void> _loadNext(MeSelection selection) async {
    if (_loading != null ||
        (_pageFailed && !_retryRequested) ||
        widget.api == null ||
        _last == null) {
      return;
    }
    _retryRequested = false;
    const families = ['considerations', 'collectives', 'resources'];
    final pending = selection.territories.where(
      (territory) =>
          territory.hasMore && families.contains(territory.presentation.key),
    );
    if (pending.isEmpty) return;
    final territory = pending.first.presentation.key;
    final repository = widget.repository;
    setState(() => _loading = territory);
    try {
      final current =
          await repository.store.readProjection('personal.me') ?? _last!;
      await repository.loadMoreMe(
        api: widget.api!,
        current: current,
        territory: territory,
      );
      // The next load must never be based on the old snapshot while the
      // projection watcher is still delivering its update.
      final latest = await repository.store.readProjection('personal.me');
      if (!mounted || widget.repository != repository) return;
      _last = latest;
      setState(() {
        _loading = null;
        _pageFailed = false;
      });
    } on Object {
      if (!mounted || widget.repository != repository) return;
      setState(() {
        _loading = null;
        _pageFailed = true;
      });
    }
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
}

class MeView extends StatefulWidget {
  const MeView({
    super.key,
    required this.selection,
    this.onOpenDestination,
    this.mediaApi,
    this.avatarProfileId,
    this.avatarRevision,
    this.onReachEnd,
    this.onRetry,
    this.loadingMore = false,
    this.loadFailed = false,
  });

  final MeSelection selection;
  final bool Function(StructuredDestination destination)? onOpenDestination;
  final MakoloApiClient? mediaApi;
  final String? avatarProfileId;
  final Object? avatarRevision;
  final VoidCallback? onReachEnd;
  final VoidCallback? onRetry;
  final bool loadingMore;
  final bool loadFailed;

  @override
  State<MeView> createState() => _MeViewState();
}

class _MeViewState extends State<MeView> {
  final ScrollController _controller = ScrollController();

  @override
  void initState() {
    super.initState();
    _controller.addListener(_checkEnd);
  }

  void _checkEnd() {}


  @override
  void didUpdateWidget(covariant MeView oldWidget) {
    super.didUpdateWidget(oldWidget);

  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final useTwoTerritories =
            constraints.maxWidth >= MakoloLayout.meTwoColumnMinWidth &&
            MediaQuery.textScalerOf(context).scale(16) <= 21 &&
            widget.selection.contentfulTerritoryCount >= 2;
        return MakoloSurfaceStateView(
          state: widget.selection.state,
          content: _MeField(
            selection: widget.selection,
            controller: _controller,
            mediaApi: widget.mediaApi,
            avatarProfileId: widget.avatarProfileId,
            avatarRevision: widget.avatarRevision,
            useTwoTerritories: useTwoTerritories,
            onSelectItem: _selectItem,
            loadingMore: widget.loadingMore,
            loadFailed: widget.loadFailed,
            onRetry: widget.onRetry,
            hasMore: widget.selection.territories.any((t) => t.hasMore),
            hasOwnerNavigation: widget.onOpenDestination != null,
            canConfirmExhaustion:
                widget.onReachEnd != null ||
                widget.selection.territories.every((t) => !t.hasMore),
          ),
        );
      },
    );
  }

  void _selectItem(MeItemPresentation item) {
    if (!item.canOpen) return;
    widget.onOpenDestination?.call(item.destination);
    // No generic fallback: the owner either opens its native route, or
    // the N1 fact stays in place until that owner has a real client screen.
  }
}

class _MeFirstAvailability extends StatelessWidget {
  const _MeFirstAvailability({
    required this.loading,
    required this.offline,
    required this.unavailable,
  });

  final bool loading;
  final bool offline;
  final bool unavailable;

  @override
  Widget build(BuildContext context) {
    final message = loading ? 'Chargement…' : 'Profil indisponible.';

    return MakoloContentFrame(
      child: SingleChildScrollView(
        key: const Key('me-first-availability'),
        padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              message,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: MakoloSpacing.strong),
            _MeLoadingSection(title: 'Identité', loading: loading),
            const SizedBox(height: MakoloSpacing.lg),
            _MeLoadingSection(title: 'Passeport Makolo', loading: loading),
            const SizedBox(height: MakoloSpacing.lg),
            _MeLoadingSection(
              title: 'Ce qui compte pour moi',
              loading: loading,
            ),
            const SizedBox(height: MakoloSpacing.lg),
            _MeLoadingSection(title: 'Mes collectifs', loading: loading),
            const SizedBox(height: MakoloSpacing.lg),
            _MeLoadingSection(title: 'Mes accès', loading: loading),
            const SizedBox(height: MakoloSpacing.lg),
            _MeLoadingSection(title: 'Mes ressources', loading: loading),
          ],
        ),
      ),
    );
  }
}

class _MeLoadingSection extends StatelessWidget {
  const _MeLoadingSection({required this.title, required this.loading});

  final String title;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return MakoloSection(
      title: title,
      padding: EdgeInsets.zero,
      child: loading
          ? const MakoloSkeleton(lines: 2)
          : Text(
              'Pas encore disponible ici.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
    );
  }
}

class _MeField extends StatelessWidget {
  const _MeField({
    required this.selection,
    required this.controller,
    required this.mediaApi,
    this.avatarProfileId,
    this.avatarRevision,
    required this.useTwoTerritories,
    required this.onSelectItem,
    required this.loadingMore,
    required this.loadFailed,
    required this.onRetry,
    required this.hasMore,
    required this.hasOwnerNavigation,
    required this.canConfirmExhaustion,
  });

  final MeSelection selection;
  final ScrollController controller;
  final MakoloApiClient? mediaApi;
  final String? avatarProfileId;
  final Object? avatarRevision;
  final bool useTwoTerritories;
  final ValueChanged<MeItemPresentation> onSelectItem;
  final bool loadingMore;
  final bool loadFailed;
  final VoidCallback? onRetry;
  final bool hasMore;
  final bool hasOwnerNavigation;
  final bool canConfirmExhaustion;

  @override
  Widget build(BuildContext context) {
    final edge = useTwoTerritories ? 0.0 : MakoloLayout.edgeCompact;
    final territories = <Widget>[
      for (final territory in selection.territories) ...[
        if (territory.presentation.key == 'resources' && selection.canOpenHistory)
          _MeHistorySection(
            edge: edge,
            onOpen: hasOwnerNavigation
                ? () => onSelectItem(const MeItemPresentation(
                    destination: StructuredDestination(kind: 'history', id: 'me'),
                    title: 'Mon historique', canOpen: true,
                  ))
                : null,
          ),
        _MeTerritory(
          key: ValueKey('me-territory-${territory.presentation.key}'),
          territory: territory,
          onSelectItem: onSelectItem,
          hasOwnerNavigation: hasOwnerNavigation,
          mediaApi: mediaApi,
          edge: edge,
        ),
      ],
      if (selection.canOpenHistory && !selection.territories.any((t) => t.presentation.key == 'resources'))
        _MeHistorySection(
          edge: edge,
          onOpen: hasOwnerNavigation
              ? () => onSelectItem(
                  const MeItemPresentation(
                    destination: StructuredDestination(kind: 'history', id: 'me'),
                    title: 'Mon historique', canOpen: true,
                  ),
                )
              : null,
        ),
    ];

    final field = ListView(
      key: const PageStorageKey<String>('me-field-scroll'),
      controller: controller,
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(
        top: MakoloSpacing.sm,
        bottom: MakoloSpacing.xl,
      ),
      children: [
        Padding(
          padding: EdgeInsets.symmetric(horizontal: edge),
          child: _MeIdentity(
            selection: selection,
            avatarProfileId: avatarProfileId,
            avatarApi: mediaApi,
            avatarRevision: avatarRevision,
            onAvatarTap: hasOwnerNavigation
                ? () => onSelectItem(
                    const MeItemPresentation(
                      destination: StructuredDestination(kind: 'avatar_edit', id: 'me'),
                      title: 'Modifier la photo', canOpen: true,
                    ),
                  )
                : null,
            onEdit: hasOwnerNavigation
                ? () => onSelectItem(
                    const MeItemPresentation(
                      destination: StructuredDestination(
                        kind: 'profile_self',
                        id: 'me',
                      ),
                      title: 'Modifier mon passeport',
                      canOpen: true,
                    ),
                  )
                : null,
          ),
        ),
        const SizedBox(height: MakoloSpacing.inner),
        if (useTwoTerritories)
          Padding(
            padding: EdgeInsets.symmetric(horizontal: edge),
            child: MakoloAdaptiveGrid(
              key: const Key('me-territories-wide'),
              minUnitWidth: 320,
              maxColumns: 2,
              children: territories,
            ),
          )
        else
          Column(
            key: const Key('me-territories-compact'),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (var index = 0; index < territories.length; index++) ...[
                territories[index],
                if (index != territories.length - 1)
                  const SizedBox(height: MakoloSpacing.inner),
              ],
            ],
          ),

      ],
    );
    if (useTwoTerritories) {
      return MakoloContentFrame(child: field);
    }
    return field;
  }
}

class _MeIdentity extends StatelessWidget {
  const _MeIdentity({required this.selection, this.onEdit, this.onAvatarTap,
    this.avatarProfileId, this.avatarApi, this.avatarRevision});

  final MeSelection selection;
  final VoidCallback? onEdit;
  final VoidCallback? onAvatarTap;
  final String? avatarProfileId;
  final MakoloApiClient? avatarApi;
  final Object? avatarRevision;

  @override
  Widget build(BuildContext context) {
    if (selection.identityState.failure == MakoloFailureCue.blocking) {
      return const MakoloErrorState(
        message: 'Votre identité est momentanément indisponible.',
      );
    }

    final theme = Theme.of(context);
    final name = selection.presentation.identityLabel;
    return Semantics(
      container: true,
      label: name,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.compact),
        child: Row(
          children: [
            Semantics(
              button: onAvatarTap != null,
              label: 'Modifier ma photo',
              child: InkWell(
                onTap: onAvatarTap,
                borderRadius: BorderRadius.circular(40),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    _MeAvatar(name: name, imageUrl: selection.identityAvatarUrl,
                      profileId: avatarProfileId, api: avatarApi,
                      revision: avatarRevision),
                    if (onAvatarTap != null)
                      Positioned(
                        right: -2, bottom: -2,
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primary,
                            shape: BoxShape.circle,
                            border: Border.all(color: theme.colorScheme.surface, width: 2),
                          ),
                          child: const Icon(Icons.camera_alt_rounded,
                            color: Colors.white, size: 13),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: MakoloSpacing.compact),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (selection.identitySubtitle != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      selection.identitySubtitle!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  if (selection.identityDetail != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      selection.identityDetail!,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium,
                    ),
                  ],
                ],
              ),
            ),
            if (onEdit != null)
              IconButton(
                tooltip: 'Modifier mon passeport',
                onPressed: onEdit,
                icon: const Icon(Icons.edit_outlined),
                color: theme.colorScheme.primary,
              ),
          ],
        ),
      ),
    );
  }
}

class _MeHistorySection extends StatelessWidget {
  const _MeHistorySection({required this.edge, this.onOpen});
  final double edge;
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: EdgeInsets.fromLTRB(edge, MakoloSpacing.sm,
            edge, MakoloSpacing.compact),
        child: Row(children: [
          Icon(Icons.history_rounded, color: colors.primary, size: 23),
          const SizedBox(width: MakoloSpacing.compact),
          Text('Mon historique',
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontWeight: FontWeight.w800)),
        ]),
      ),
      Material(
        color: colors.surface,
        child: InkWell(
          onTap: onOpen,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: edge, vertical: 15),
            child: Row(children: [
              Expanded(child: Text('Retrouver mon parcours',
                  style: Theme.of(context).textTheme.bodyLarge)),
              if (onOpen != null) Icon(Icons.chevron_right_rounded,
                  color: colors.onSurfaceVariant),
            ]),
          ),
        ),
      ),
    ]);
  }
}

class _MeAvatar extends StatelessWidget {
  const _MeAvatar({
    required this.name, this.imageUrl, this.profileId, this.api,
    this.revision,
  });

  final String name;
  final String? imageUrl;
  final String? profileId;
  final MakoloApiClient? api;
  final Object? revision;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final initials = name.trim().split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty).take(2)
        .map((part) => part.substring(0, 1).toUpperCase()).join();
    final placeholder = Container(
      width: 64, height: 64, alignment: Alignment.center,
      decoration: BoxDecoration(
        color: theme.colorScheme.primary.withValues(alpha: 0.10),
        shape: BoxShape.circle,
      ),
      child: Text(initials.isEmpty ? 'M' : initials,
        style: theme.textTheme.titleLarge?.copyWith(
          color: theme.colorScheme.primary, fontWeight: FontWeight.w700)),
    );
    return ExcludeSemantics(child: ClipOval(
      child: ProfileAvatarImage(
        profileId: profileId, api: api, url: imageUrl,
        revision: revision, size: 64,
        fallback: placeholder,
      ),
    ));
  }
}

class _MeTerritory extends StatelessWidget {
  const _MeTerritory({
    super.key,
    required this.territory,
    required this.onSelectItem,
    required this.hasOwnerNavigation,
    required this.mediaApi,
    required this.edge,
  });

  final MeTerritorySelection territory;
  final ValueChanged<MeItemPresentation> onSelectItem;
  final bool hasOwnerNavigation;
  final MakoloApiClient? mediaApi;
  final double edge;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final presentation = territory.presentation;
    final isPassport = presentation.key == 'passport';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: EdgeInsets.fromLTRB(edge, MakoloSpacing.sm,
              edge, MakoloSpacing.compact),
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: presentation.key == 'considerations' && hasOwnerNavigation
                  ? () => onSelectItem(
                      const MeItemPresentation(
                        destination: StructuredDestination(
                          kind: 'considerations', id: 'mine',
                        ),
                        title: 'Ce qui compte pour moi',
                        canOpen: true,
                      ),
                    )
                  : null,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(children: [
                  Icon(_iconForTerritory(presentation.key),
                      color: color.primary, size: 23),
                  const SizedBox(width: MakoloSpacing.compact),
                  Expanded(
                    child: Text(presentation.label,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800),
                    ),
                  ),
                  if (territory.totalCount > 0)
                    Text('${territory.totalCount}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: color.onSurfaceVariant,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  if (presentation.key == 'considerations' && hasOwnerNavigation)
                    const Padding(
                      padding: EdgeInsetsDirectional.only(start: 6),
                      child: Icon(Icons.chevron_right_rounded),
                    ),
                ]),
              ),
            ),
          ),
        ),
        if (isPassport)
          Padding(
            padding: EdgeInsets.symmetric(horizontal: edge),
            child: _body(context),
          )
        else
          Material(
            color: color.surface,
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: edge,
                vertical: MakoloSpacing.sm,
              ),
              child: _body(context),
            ),
          ),
      ],
    );
  }

  IconData _iconForTerritory(String key) => switch (key) {
    'passport' => Icons.badge_outlined,
    'considerations' => Icons.interests_outlined,
    'collectives' => Icons.groups_outlined,
    'accesses' => Icons.confirmation_number_outlined,
    'resources' => Icons.folder_copy_outlined,
    'support' => Icons.handshake_outlined,
    _ => Icons.grid_view_outlined,
  };

  Widget _body(BuildContext context) {
    if (territory.presentation.state.failure == MakoloFailureCue.blocking) {
      return const MakoloErrorState(
        message: 'Cette section est momentanément indisponible.',
      );
    }
    return switch (territory.presentation.key) {
      'passport' => _passport(context),
      'considerations' => _considerations(context),
      'collectives' => _collectives(context),
      'resources' => _resources(context),
      'support' => _support(context),
      _ => _generic(context),
    };
  }

  Widget _passport(BuildContext context) {
    if (!territory.hasContent) {
      return _empty(context, 'Aucun passeport disponible.');
    }
    final firstItem = territory.items.isNotEmpty ? territory.items.first : null;
    final onOpen = firstItem != null && firstItem.canOpen && hasOwnerNavigation
        ? () => onSelectItem(firstItem)
        : null;
    final textTheme = Theme.of(context).textTheme;
    return Semantics(
      button: onOpen != null,
      label: 'Passeport Makolo. Ouvrir mon passeport.',
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        clipBehavior: Clip.antiAlias,
        child: Ink(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [MakoloColors.indigo, MakoloColors.deep],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.all(Radius.circular(MakoloRadii.card)),
          ),
          child: InkWell(
            onTap: onOpen,
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.md,
                vertical: MakoloSpacing.md,
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.badge_outlined,
                    color: Colors.white,
                    size: 32,
                  ),
                  const SizedBox(width: MakoloSpacing.compact),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Mon passeport',
                          style: textTheme.titleMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: MakoloSpacing.xs),
                        Text(
                          'À partager selon votre choix',
                          style: textTheme.bodySmall?.copyWith(
                            color: Colors.white.withValues(alpha: 0.9),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (onOpen != null) ...[
                    const SizedBox(width: MakoloSpacing.sm),
                    const Icon(
                      Icons.arrow_forward_rounded,
                      color: Colors.white,
                      size: 24,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _considerations(BuildContext context) {
    final saved = territory.items.where((item) =>
        item.destination.kind == 'activity').take(3).toList();
    final interests = territory.items.where((item) =>
        item.destination.kind == 'topic').take(4).toList();
    final openTo = territory.items.where((item) =>
        item.destination.kind == 'open_to').take(3).toList();
    final colors = Theme.of(context).colorScheme;
    final canNavigate = hasOwnerNavigation;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (interests.isNotEmpty || openTo.isNotEmpty) ...[
        Wrap(spacing: 7, runSpacing: 6, children: [
          for (final item in [...interests, ...openTo])
            _MeChip(item: item, onTap: null),
        ]),
        const SizedBox(height: MakoloSpacing.compact),
      ],
      if (saved.isNotEmpty) ...[
        Text('Mes enregistrements', style: Theme.of(context).textTheme.labelLarge
          ?.copyWith(fontWeight: FontWeight.w800,
            color: colors.onSurfaceVariant)),
        for (final item in saved)
          _MeConsideration(
            key: ValueKey('me-item-${item.destination.kind}-${item.destination.id}'),
            item: item,
            mediaApi: mediaApi,
            onTap: item.canOpen && canNavigate
                ? () => onSelectItem(item) : null,
          ),
      ],
      if (canNavigate)
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: TextButton.icon(
            onPressed: () => onSelectItem(
              const MeItemPresentation(
                destination: StructuredDestination(kind: 'saved_collection', id: 'mine'),
                title: 'Mes enregistrements', canOpen: true,
              ),
            ),
            icon: DiscoveryOrbitIcon(saved: true,
              color: Theme.of(context).colorScheme.primary),
            label: Text(territory.savedCount > 0
                ? 'Voir les ${territory.savedCount} enregistrements'
                : 'Mes enregistrements'),
          ),
        ),
      if (territory.items.isEmpty && !canNavigate)
        _empty(context, 'Rien de déclaré pour le moment.'),
    ]);
  }

  Widget _collectives(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Aucun collectif associé.');
    }
    return Column(
      children: [
        for (final item in territory.items)
          _MeIdentityRow(
            item: item,
            onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item)
                : null,
          ),
      ],
    );
  }

  Widget _resources(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Aucune ressource disponible.');
    }
    return Column(
      children: [
        for (final item in territory.items)
          _MeResourceRow(
            item: item,
            onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item)
                : null,
          ),
      ],
    );
  }

  Widget _support(BuildContext context) {
    if (territory.items.isEmpty) return const SizedBox.shrink();
    return Column(
      children: [
        for (final item in territory.items)
          _MeIdentityRow(
            item: item,
            onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item)
                : null,
          ),
      ],
    );
  }

  Widget _generic(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Rien ici pour le moment.');
    }
    return Column(
      children: [
        for (final item in territory.items)
          _MeIdentityRow(
            item: item,
            onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item)
                : null,
          ),
      ],
    );
  }

  Widget _empty(BuildContext context, String message) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.compact),
      child: Text(
        message,
        style: Theme.of(context).textTheme.bodyMedium
            ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
      ),
    );
  }
}

class _MeChip extends StatelessWidget {
  const _MeChip({required this.item, this.onTap});

  final MeItemPresentation item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.primary.withValues(alpha: 0.07),
      borderRadius: BorderRadius.circular(MakoloRadii.pill),
      child: InkWell(
        borderRadius: BorderRadius.circular(MakoloRadii.pill),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: MakoloSpacing.compact,
            vertical: MakoloSpacing.sm,
          ),
          child: Text(
            item.title,
            style: Theme.of(context).textTheme.bodyMedium
                ?.copyWith(color: scheme.primary, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }
}

class _MeConsideration extends StatelessWidget {
  const _MeConsideration({
    super.key,
    required this.item,
    required this.onTap,
    this.mediaApi,
  });

  final MeItemPresentation item;
  final VoidCallback? onTap;
  final MakoloApiClient? mediaApi;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isSaved = item.destination.kind == 'activity';
    return Semantics(
      button: onTap != null,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                vertical: MakoloSpacing.compact,
              ),
              child: Row(
                children: [
                  if (isSaved) ...[
                    const SizedBox(
                      width: 24,
                      height: 24,
                      child: Center(child: _MeSavedOrbit()),
                    ),
                    const SizedBox(width: MakoloSpacing.compact),
                  ],
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.title,
                          style: Theme.of(context).textTheme.bodyLarge
                              ?.copyWith(fontWeight: FontWeight.w600),
                        ),
                        if (item.subtitle != null) ...[
                          const SizedBox(height: MakoloSpacing.xs),
                          Text(
                            item.subtitle!,
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(color: scheme.onSurfaceVariant),
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (isSaved &&
                      mediaApi != null &&
                      item.mediaPath != null) ...[
                    const SizedBox(width: MakoloSpacing.sm),
                    _MeRecognitionThumbnail(
                      key: ValueKey(item.mediaPath),
                      api: mediaApi!,
                      path: item.mediaPath!,
                      alt: item.mediaAlt ?? item.title,
                    ),
                  ],
                  if (onTap != null) ...[
                    const SizedBox(width: MakoloSpacing.sm),
                    Icon(
                      Icons.chevron_right_rounded,
                      size: 21,
                      color: scheme.onSurfaceVariant,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Reuses the published-media transport; no token in a widget or raw file URL.
class _MeRecognitionThumbnail extends StatefulWidget {
  const _MeRecognitionThumbnail({
    super.key,
    required this.api,
    required this.path,
    required this.alt,
  });

  final MakoloApiClient api;
  final String path;
  final String alt;

  @override
  State<_MeRecognitionThumbnail> createState() =>
      _MeRecognitionThumbnailState();
}

class _MeRecognitionThumbnailState extends State<_MeRecognitionThumbnail> {
  late Future<Uint8List> _bytes;

  @override
  void initState() {
    super.initState();
    _bytes = widget.api.getPresentationImage(widget.path);
  }

  @override
  void didUpdateWidget(covariant _MeRecognitionThumbnail oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.path != oldWidget.path || widget.api != oldWidget.api) {
      _bytes = widget.api.getPresentationImage(widget.path);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uint8List>(
      future: _bytes,
      builder: (context, snapshot) {
        if (snapshot.hasError) return const SizedBox.shrink();
        if (!snapshot.hasData) {
          return const SizedBox(width: 72, height: 56);
        }
        return ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.memory(
            snapshot.data!,
            width: 72,
            height: 56,
            fit: BoxFit.cover,
            semanticLabel: widget.alt,
            gaplessPlayback: true,
            errorBuilder: (_, _, _) => const SizedBox.shrink(),
          ),
        );
      },
    );
  }
}

class _MeSavedOrbit extends StatelessWidget {
  const _MeSavedOrbit();

  @override
  Widget build(BuildContext context) {
    return DiscoveryOrbitIcon(
      saved: true,
      color: Theme.of(context).colorScheme.primary,
    );
  }
}

class _MeIdentityRow extends StatelessWidget {
  const _MeIdentityRow({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final initial = item.title.trim().isEmpty
        ? 'M'
        : item.title.trim().substring(0, 1).toUpperCase();
    return Material(
      color: Colors.transparent,
      child: ListTile(
        dense: true,
        minVerticalPadding: MakoloSpacing.xs,
        contentPadding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        onTap: onTap,
        leading: CircleAvatar(
          radius: 18,
          backgroundColor: scheme.primary.withValues(alpha: 0.08),
          child: Text(
            initial,
            style: Theme.of(context).textTheme.labelLarge
                ?.copyWith(color: scheme.primary, fontWeight: FontWeight.w800),
          ),
        ),
        title: Text(item.title, style: Theme.of(context).textTheme.bodyLarge),
        subtitle: item.subtitle == null ? null : Text(item.subtitle!),
        trailing: onTap == null
            ? null
            : const Icon(Icons.chevron_right_rounded, size: 21),
      ),
    );
  }
}

class _MeResourceRow extends StatelessWidget {
  const _MeResourceRow({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: Colors.transparent,
      child: ListTile(
        dense: true,
        minVerticalPadding: MakoloSpacing.xs,
        contentPadding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        onTap: onTap,
        leading: Icon(
          _iconFor(item.destination.kind),
          size: 21,
          color: scheme.primary,
        ),
        title: Text(item.title, style: Theme.of(context).textTheme.bodyLarge),
        subtitle: item.subtitle == null ? null : Text(item.subtitle!),
        trailing: onTap == null
            ? null
            : const Icon(Icons.chevron_right_rounded, size: 21),
      ),
    );
  }

  IconData _iconFor(String kind) => switch (kind) {
    'proof' => Icons.verified_outlined,
    'credential' => Icons.workspace_premium_outlined,
    'personal_asset' => Icons.folder_outlined,
    'resource_collection' => Icons.inventory_2_outlined,
    _ => Icons.description_outlined,
  };
}
