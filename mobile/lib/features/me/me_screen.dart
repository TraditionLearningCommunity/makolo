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
import '../../navigation/refresh_boundary.dart';
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
      onOpenDestination: widget.onOpenDestination,
      loadingMore: _loading != null,
      loadFailed: _pageFailed,
      onRetry: () { setState(() { _pageFailed = false; _retryRequested = true; }); _loadNext(selection); },
      onReachEnd: widget.api == null || syncStatus?.state == SyncVisualState.offline
          ? null : () => _loadNext(selection),
    );
  }

  Future<void> _loadNext(MeSelection selection) async {
    if (_loading != null || (_pageFailed && !_retryRequested) ||
        widget.api == null || _last == null) return;
    _retryRequested = false;
    const families = ['considerations', 'collectives', 'resources'];
    final pending = selection.territories.where((territory) =>
        territory.hasMore && families.contains(territory.presentation.key));
    if (pending.isEmpty) return;
    final territory = pending.first.presentation.key;
    final repository = widget.repository;
    setState(() => _loading = territory);
    try {
      final current = await repository.store.readProjection('personal.me') ?? _last!;
      await repository.loadMoreMe(
        api: widget.api!, current: current, territory: territory,
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
  const MeView({super.key, required this.selection, this.onOpenDestination,
    this.onReachEnd, this.onRetry, this.loadingMore = false, this.loadFailed = false});

  final MeSelection selection;
  final bool Function(StructuredDestination destination)? onOpenDestination;
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

  void _checkEnd() {
    if (_controller.hasClients && !widget.loadingMore && !widget.loadFailed &&
        _controller.position.extentAfter < 520) {
      widget.onReachEnd?.call();
    }
  }

  @override
  void didUpdateWidget(covariant MeView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.onReachEnd != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _checkEnd();
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final useTwoTerritories =
          constraints.maxWidth >= MakoloLayout.meTwoColumnMinWidth &&
          MediaQuery.textScalerOf(context).scale(16) <= 21 &&
          widget.selection.contentfulTerritoryCount >= 2;
      if (widget.onReachEnd != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _checkEnd();
        });
      }
      return MakoloSurfaceStateView(
        state: widget.selection.state,
        content: MakoloContentFrame(
          child: _MeField(
            selection: widget.selection,
            controller: _controller,
            useTwoTerritories: useTwoTerritories,
            onSelectItem: _selectItem,
            loadingMore: widget.loadingMore,
            loadFailed: widget.loadFailed,
            onRetry: widget.onRetry,
            hasMore: widget.selection.territories.any((t) => t.hasMore),
            hasOwnerNavigation: widget.onOpenDestination != null,
            canConfirmExhaustion: widget.onReachEnd != null ||
                (widget.selection.territories.every((t) => !t.hasMore)),
          ),
        ),
      );
    });
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
    final territories = [
      for (final territory in selection.territories)
        _MeTerritory(territory: territory, onSelectItem: onSelectItem,
          hasOwnerNavigation: hasOwnerNavigation),
    ];

    return ListView(
      key: const PageStorageKey<String>('me-field-scroll'),
      controller: controller,
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      children: [
        _MeIdentity(
          selection: selection,
          onEdit: hasOwnerNavigation ? () => onSelectItem(
            const MeItemPresentation(
              destination: StructuredDestination(kind: 'profile_self', id: 'me'),
              title: 'Mon profil',
              canOpen: true,
            ),
          ) : null,
        ),
        const SizedBox(height: MakoloSpacing.xl),
        if (useTwoTerritories)
          MakoloAdaptiveGrid(
            key: const Key('me-territories-wide'),
            minUnitWidth: 320,
            maxColumns: 2,
            children: territories,
          )
        else
          Column(
            key: const Key('me-territories-compact'),
            children: [
              for (var index = 0; index < territories.length; index++) ...[
                territories[index],
                if (index != territories.length - 1)
                  const SizedBox(height: MakoloSpacing.lg),
              ],
            ],
          ),
        const SizedBox(height: MakoloSpacing.xl),
        if (loadingMore) const Center(child: CircularProgressIndicator.adaptive())
        else if (loadFailed) Center(child: TextButton(onPressed: onRetry, child: const Text('Réessayer')))
        else if (!hasMore && canConfirmExhaustion) Center(child: Text('Vous avez tout exploré', style: Theme.of(context).textTheme.bodySmall)),
        if (hasOwnerNavigation && selection.canOpenHistory) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton.icon(
              onPressed: () => onSelectItem(const MeItemPresentation(
                destination: StructuredDestination(kind: 'history', id: 'me'),
                title: 'Historique', canOpen: true,
              )),
              icon: const Icon(Icons.history_rounded),
              label: const Text('Historique'),
            ),
          ),
        ],
      ],
    );
  }
}

class _MeIdentity extends StatelessWidget {
  const _MeIdentity({required this.selection, this.onEdit});

  final MeSelection selection;
  final VoidCallback? onEdit;

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
      header: true,
      label: name,
      child: Container(
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        decoration: BoxDecoration(
          color: theme.colorScheme.surface,
          borderRadius: BorderRadius.circular(MakoloRadii.large),
          border: Border.all(
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.65),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                _MeAvatar(name: name, imageUrl: selection.identityAvatarUrl),
                const SizedBox(width: MakoloSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: theme.textTheme.headlineMedium,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (selection.identitySubtitle != null) ...[
                        const SizedBox(height: MakoloSpacing.xs),
                        Text(
                          selection.identitySubtitle!,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            if (selection.identityDetail != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Text(
                selection.identityDetail!,
                style: theme.textTheme.bodyMedium,
              ),
            ],
            if (onEdit != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton.icon(
                  onPressed: onEdit,
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Modifier'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MeAvatar extends StatelessWidget {
  const _MeAvatar({required this.name, this.imageUrl});

  final String name;
  final String? imageUrl;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final initials = name.trim().split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .take(2)
        .map((part) => part.substring(0, 1).toUpperCase())
        .join();
    final placeholder = Container(
      width: 76,
      height: 76,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: theme.colorScheme.primary.withValues(alpha: 0.10),
        shape: BoxShape.circle,
      ),
      child: Text(
        initials.isEmpty ? 'M' : initials,
        style: theme.textTheme.titleLarge?.copyWith(
          color: theme.colorScheme.primary,
          fontWeight: FontWeight.w700,
        ),
      ),
    );

    final url = imageUrl;
    final parsed = url == null ? null : Uri.tryParse(url);
    if (parsed == null ||
        !(parsed.scheme == 'https' || parsed.scheme == 'http') ||
        parsed.host.isEmpty) {
      return ExcludeSemantics(child: placeholder);
    }
    return ExcludeSemantics(
      child: ClipOval(
        child: Image.network(
          url!,
          width: 76,
          height: 76,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => placeholder,
        ),
      ),
    );
  }
}

class _MeTerritory extends StatelessWidget {
  const _MeTerritory({required this.territory, required this.onSelectItem,
    required this.hasOwnerNavigation});

  final MeTerritorySelection territory;
  final ValueChanged<MeItemPresentation> onSelectItem;
  final bool hasOwnerNavigation;

  @override
  Widget build(BuildContext context) {
    final presentation = territory.presentation;

    final colors = Theme.of(context).colorScheme;
    final hasContent = territory.hasContent;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: colors.primary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(MakoloRadii.control),
              ),
              child: Icon(_iconForTerritory(presentation.key), color: colors.primary, size: 22),
            ),
            const SizedBox(width: MakoloSpacing.compact),
            Expanded(
              child: Text(
                presentation.label,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            if (territory.totalCount > 0)
              Text(
                '${territory.totalCount}',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: colors.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
          ],
        ),
        const SizedBox(height: MakoloSpacing.compact),
        AnimatedContainer(
          duration: MakoloMotion.effective(context, MakoloMotion.short),
          decoration: BoxDecoration(
            color: hasContent ? colors.surface : colors.surface.withValues(alpha: 0.56),
            border: Border.all(color: colors.outlineVariant.withValues(alpha: 0.65)),
            borderRadius: BorderRadius.circular(MakoloRadii.card),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: MakoloSpacing.md,
            vertical: MakoloSpacing.compact,
          ),
          child: _body(context),
        ),
        if (territory.hasMore) ...[
          const SizedBox(height: MakoloSpacing.xs),
          Padding(
            padding: const EdgeInsetsDirectional.only(start: MakoloSpacing.sm),
            child: Text(
              'Aperçu',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
          ),
        ],
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
    final state = territory.presentation.state;

    if (state.failure == MakoloFailureCue.blocking) {
      return const MakoloErrorState(
        message:
            'Cette section n’est pas disponible '
            'pour le moment.',
      );
    }

    final content = switch (territory.presentation.key) {
      'passport' => _passport(context),
      'considerations' => _considerations(context),
      'collectives' => _collectives(context),
      'resources' => _resources(context),
      'support' => _support(context),
      _ => _generic(context),
    };

    return content;
  }

  Widget _passport(BuildContext context) {
    if (!territory.hasContent) {
      return _empty(context, 'Aucun passeport disponible.');
    }

    final firstItem = territory.items.isNotEmpty ? territory.items.first : null;
    return Semantics(
      label: 'Passeport Makolo disponible',
      child: Container(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [MakoloColors.indigo, MakoloColors.deep],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(MakoloRadii.card),
        ),
        child: Row(
          children: [
            const Icon(Icons.badge_outlined, color: Colors.white, size: 40),
            const SizedBox(width: MakoloSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Votre passeport',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    'À partager selon votre choix',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.white.withValues(alpha: 0.85),
                    ),
                  ),
                ],
              ),
            ),
            if (firstItem != null)
              IconButton(
                tooltip: 'Ouvrir le passeport',
                onPressed: firstItem.canOpen && hasOwnerNavigation
                    ? () => onSelectItem(firstItem) : null,
                icon: const Icon(Icons.arrow_forward, color: Colors.white),
              ),
          ],
        ),
      ),
    );
  }

  Widget _considerations(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Rien de déclaré pour le moment.');
    }

    const families = <(String, List<String>)>[
      ('Intérêts', ['topic']),
      ('Ouvert à', ['open_to']),
      ('Veilles', ['watch']),
      ('Enregistrés', ['activity']),
      ('Espaces suivis', ['space']),
      ('Personnes suivies', ['profile']),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final family in families)
          if (territory.items.any((item) => family.$2.contains(item.destination.kind))) ...[
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.sm, bottom: MakoloSpacing.xs),
              child: Text(
                family.$1,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            for (final item in territory.items.where((item) => family.$2.contains(item.destination.kind)))
              _MeConsideration(item: item, onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item) : null),
          ],
      ],
    );
  }

  Widget _collectives(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Aucun collectif associé.');
    }

    return Column(
      children: [
        for (final item in territory.items)
          _MeIdentityRow(item: item, onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item) : null),
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
          _MeResourceRow(item: item, onTap: item.canOpen && hasOwnerNavigation
                ? () => onSelectItem(item) : null),
      ],
    );
  }

  Widget _support(BuildContext context) {
    if (territory.items.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      children: [
        for (final item in territory.items)
          _MeIdentityRow(item: item, onTap: () => onSelectItem(item)),
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
          _MeIdentityRow(item: item, onTap: () => onSelectItem(item)),
      ],
    );
  }

  Widget _empty(BuildContext context, String message) {
    return Text(
      message,
      style: Theme.of(context).textTheme.bodyMedium
          ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
    );
  }
}

class _MeConsideration extends StatelessWidget {
  const _MeConsideration({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final semanticLabel = [
      item.title,
      item.subtitle,
    ].whereType<String>().join('. ');

    return Semantics(
      button: onTap != null,
      label: semanticLabel,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MakoloRadii.control),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.title, style: Theme.of(context).textTheme.bodyLarge),
                if (item.subtitle != null) ...[
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    item.subtitle!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
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

class _MeIdentityRow extends StatelessWidget {
  const _MeIdentityRow({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final initial = item.title.trim().isEmpty
        ? 'M'
        : item.title.trim().substring(0, 1).toUpperCase();

    return ListTile(
      contentPadding: EdgeInsets.zero,
      minVerticalPadding: MakoloSpacing.sm,
      onTap: onTap,
      leading: CircleAvatar(
        backgroundColor: color.primary.withValues(alpha: 0.10),
        child: Text(
          initial,
          style: TextStyle(color: color.primary, fontWeight: FontWeight.w700),
        ),
      ),
      title: Text(item.title),
      subtitle: item.subtitle == null ? null : Text(item.subtitle!),
      trailing: onTap == null ? null : const Icon(Icons.chevron_right_rounded),
    );
  }
}

class _MeResourceRow extends StatelessWidget {
  const _MeResourceRow({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      minVerticalPadding: MakoloSpacing.sm,
      onTap: onTap,
      leading: Icon(_iconFor(item.destination.kind)),
      title: Text(item.title),
      subtitle: item.subtitle == null ? null : Text(item.subtitle!),
      trailing: onTap == null ? null : const Icon(Icons.chevron_right_rounded),
    );
  }

  IconData _iconFor(String kind) {
    return switch (kind) {
      'proof' => Icons.verified_outlined,
      'credential' => Icons.workspace_premium_outlined,
      'personal_asset' => Icons.folder_outlined,
      'resource_collection' => Icons.inventory_2_outlined,
      _ => Icons.description_outlined,
    };
  }
}

