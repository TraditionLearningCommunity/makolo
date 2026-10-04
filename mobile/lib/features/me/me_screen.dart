import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../navigation/refresh_boundary.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'me_selector.dart';

class MeScreen extends StatefulWidget {
  const MeScreen({super.key, required this.repository, this.now});

  final PersonalRepository repository;
  final DateTime Function()? now;

  @override
  State<MeScreen> createState() => _MeScreenState();
}

class _MeScreenState extends State<MeScreen> {
  late Stream<StoredProjection?> _projectionStream;
  late Stream<OwnerSourceState> _sourceStream;

  @override
  void initState() {
    super.initState();
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant MeScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
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

    return MeView(selection: selection);
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
  const MeView({super.key, required this.selection});

  final MeSelection selection;

  @override
  State<MeView> createState() => _MeViewState();
}

class _MeViewState extends State<MeView> {
  final ScrollController _controller = ScrollController();
  StructuredDestination? _selectedDestination;

  MeItemPresentation? get _selectedItem {
    final selected = _selectedDestination;
    if (selected == null) {
      return null;
    }

    for (final territory in widget.selection.territories) {
      for (final item in territory.items) {
        if (_sameDestination(item.destination, selected)) {
          return item;
        }
      }
    }

    return null;
  }

  @override
  void didUpdateWidget(covariant MeView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_selectedDestination != null && _selectedItem == null) {
      _selectedDestination = null;
    }
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
            widget.selection.contentfulTerritoryCount >= 2;
        final selected = _selectedItem;

        final field = MakoloContentFrame(
          child: _MeField(
            selection: widget.selection,
            controller: _controller,
            useTwoTerritories: useTwoTerritories,
            onSelectItem: _selectItem,
          ),
        );

        final content = selected == null
            ? field
            : MakoloAdaptiveSplit(
                splitAt: MakoloLayout.meTwoColumnMinWidth,
                field: field,
                focus: MakoloContentFrame(
                  child: _MeDepth(item: selected, onClose: _closeDepth),
                ),
                narrow: MakoloContentFrame(
                  child: _MeDepth(item: selected, onClose: _closeDepth),
                ),
              );

        return PopScope<Object?>(
          canPop: _selectedDestination == null,
          onPopInvokedWithResult: (didPop, result) {
            if (!didPop && _selectedDestination != null) {
              _closeDepth();
            }
          },
          child: MakoloSurfaceStateView(
            state: widget.selection.state,
            recoverableErrorMessage: 'Mise à jour momentanément indisponible.',
            content: content,
          ),
        );
      },
    );
  }

  void _selectItem(MeItemPresentation item) {
    setState(() => _selectedDestination = item.destination);
  }

  void _closeDepth() {
    if (_selectedDestination == null) {
      return;
    }
    setState(() => _selectedDestination = null);
  }

  bool _sameDestination(
    StructuredDestination left,
    StructuredDestination right,
  ) {
    return left.kind == right.kind && left.id == right.id;
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
    final message = offline
        ? 'Une première connexion est nécessaire '
              'pour rendre ces territoires disponibles ici.'
        : unavailable
        ? 'Ces territoires ne sont pas disponibles '
              'sur cet appareil pour le moment.'
        : 'Makolo prépare ce qui est déjà en place autour de vous.';

    return MakoloContentFrame(
      child: SingleChildScrollView(
        key: const Key('me-first-availability'),
        padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Moi', style: Theme.of(context).textTheme.headlineLarge),
            const SizedBox(height: MakoloSpacing.sm),
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
  });

  final MeSelection selection;
  final ScrollController controller;
  final bool useTwoTerritories;
  final ValueChanged<MeItemPresentation> onSelectItem;

  @override
  Widget build(BuildContext context) {
    final territories = [
      for (final territory in selection.territories)
        _MeTerritory(territory: territory, onSelectItem: onSelectItem),
    ];

    return ListView(
      key: const PageStorageKey<String>('me-field-scroll'),
      controller: controller,
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      children: [
        _MeIdentity(selection: selection),
        const SizedBox(height: MakoloSpacing.strong),
        Text(
          'Déjà en place',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: MakoloSpacing.xs),
        Text(
          'Ce qui est déjà là pour faciliter la suite.',
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: MakoloSpacing.lg),
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
      ],
    );
  }
}

class _MeIdentity extends StatelessWidget {
  const _MeIdentity({required this.selection});

  final MeSelection selection;

  @override
  Widget build(BuildContext context) {
    if (selection.identityState.failure == MakoloFailureCue.blocking) {
      return const MakoloErrorState(
        message:
            'Votre identité ne peut pas être présentée '
            'correctement pour le moment.',
      );
    }

    return Semantics(
      container: true,
      header: true,
      label: selection.presentation.identityLabel,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Moi', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            selection.presentation.identityLabel,
            style: Theme.of(context).textTheme.headlineLarge,
          ),
          if (selection.identitySubtitle != null) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              selection.identitySubtitle!,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (selection.identityDetail != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(selection.identityDetail!),
          ],
        ],
      ),
    );
  }
}

class _MeTerritory extends StatelessWidget {
  const _MeTerritory({required this.territory, required this.onSelectItem});

  final MeTerritorySelection territory;
  final ValueChanged<MeItemPresentation> onSelectItem;

  @override
  Widget build(BuildContext context) {
    final presentation = territory.presentation;

    return MakoloSection(
      title: presentation.label,
      description: presentation.summary,
      padding: EdgeInsets.zero,
      child: _body(context),
    );
  }

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

    final cues = <Widget>[
      if (state.freshness != MakoloFreshnessCue.unknown &&
          state.freshness != MakoloFreshnessCue.current)
        MakoloFreshnessNotice(freshness: state.freshness),
      if (state.reachability == MakoloReachabilityCue.temporarilyUnavailable)
        const MakoloNotice(
          message: 'Contenu déjà disponible sur cet appareil.',
          kind: MakoloNoticeKind.warning,
        ),
    ];

    if (cues.isEmpty) {
      return content;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final cue in cues) ...[
          cue,
          const SizedBox(height: MakoloSpacing.sm),
        ],
        content,
      ],
    );
  }

  Widget _passport(BuildContext context) {
    if (!territory.hasContent) {
      return _empty(context, 'Aucun Passeport disponible ici pour le moment.');
    }

    return MakoloCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.badge_outlined,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: MakoloSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Disponible',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.xs),
                Text(
                  'Une vue de ce qui peut vous '
                  'représenter selon le contexte.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _considerations(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Rien de déclaré pour le moment.');
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var index = 0; index < territory.items.length; index++) ...[
          _MeConsideration(
            item: territory.items[index],
            onTap: () => onSelectItem(territory.items[index]),
          ),
          if (index != territory.items.length - 1)
            const Divider(height: MakoloSpacing.lg),
        ],
      ],
    );
  }

  Widget _collectives(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Aucun collectif lié pour le moment.');
    }

    return Column(
      children: [
        for (final item in territory.items)
          _MeIdentityRow(item: item, onTap: () => onSelectItem(item)),
      ],
    );
  }

  Widget _resources(BuildContext context) {
    if (territory.items.isEmpty) {
      return _empty(context, 'Aucune ressource disponible ici.');
    }

    return Column(
      children: [
        for (final item in territory.items)
          _MeResourceRow(item: item, onTap: () => onSelectItem(item)),
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
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final semanticLabel = [
      item.title,
      item.subtitle,
    ].whereType<String>().join('. ');

    return Semantics(
      button: true,
      label: semanticLabel,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MakoloRadii.control),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    item.title,
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ),
                if (item.subtitle != null)
                  Text(
                    item.subtitle!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
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
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      minVerticalPadding: MakoloSpacing.sm,
      onTap: onTap,
      leading: const Icon(Icons.group_outlined),
      title: Text(item.title),
      subtitle: item.subtitle == null ? null : Text(item.subtitle!),
      trailing: const Icon(Icons.chevron_right_rounded),
    );
  }
}

class _MeResourceRow extends StatelessWidget {
  const _MeResourceRow({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      minVerticalPadding: MakoloSpacing.sm,
      onTap: onTap,
      leading: Icon(_iconFor(item.destination.kind)),
      title: Text(item.title),
      subtitle: item.subtitle == null ? null : Text(item.subtitle!),
      trailing: const Icon(Icons.chevron_right_rounded),
    );
  }

  IconData _iconFor(String kind) {
    return switch (kind) {
      'proof' => Icons.verified_outlined,
      'credential' => Icons.workspace_premium_outlined,
      _ => Icons.description_outlined,
    };
  }
}

class _MeDepth extends StatelessWidget {
  const _MeDepth({required this.item, required this.onClose});

  final MeItemPresentation item;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      key: const Key('me-depth-scroll'),
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      child: MakoloFocusPane(
        child: FocusTraversalGroup(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton.icon(
                  onPressed: onClose,
                  icon: const Icon(Icons.arrow_back_rounded),
                  label: const Text('Moi'),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              Semantics(
                header: true,
                child: Text(
                  item.title,
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
              ),
              if (item.subtitle != null) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(
                  item.subtitle!,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              if (item.metadata.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.lg),
                MakoloMetadata(
                  items: [
                    for (final label in item.metadata)
                      MakoloMetadataItem(label),
                  ],
                ),
              ],
              if (_contextMessage(item.destination.kind)
                  case final message?) ...[
                const SizedBox(height: MakoloSpacing.xl),
                Text(message, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String? _contextMessage(String kind) {
    return switch (kind.toLowerCase()) {
      'personal_asset' => null,
      'proof' =>
        'Cette preuve fait partie de ce qui '
            'est déjà établi autour de vous.',
      'credential' =>
        'Ce titre fait partie de ce qui '
            'vous a déjà été délivré.',
      'group' || 'team' => 'Votre lien avec ce collectif est visible ici.',
      'space' =>
        'Ce contexte est visible ici selon '
            'les droits déjà établis par Makolo.',
      _ => null,
    };
  }
}
