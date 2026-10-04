import 'package:flutter/material.dart';

import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/presentation_media.dart';
import '../../design/surface_states.dart';
import '../../platform/maps/makolo_map_view.dart';
import '../../platform/maps/map_runtime_config.dart';
import 'discovery_selector.dart';

typedef DiscoveryOpenItem = void Function(DiscoveryItemPresentation item);

class DiscoveryExplorationView extends StatefulWidget {
  const DiscoveryExplorationView({
    super.key,
    required this.selection,
    required this.onOpen,
    this.onPage,
    this.onRetry,
    this.onResetCriteria,
  });

  final DiscoveryFieldSelection selection;
  final DiscoveryOpenItem onOpen;
  final ValueChanged<int>? onPage;
  final VoidCallback? onRetry;
  final VoidCallback? onResetCriteria;

  @override
  State<DiscoveryExplorationView> createState() =>
      _DiscoveryExplorationViewState();
}

class _DiscoveryExplorationViewState extends State<DiscoveryExplorationView> {
  String? _focusedCandidateKey;

  @override
  void didUpdateWidget(covariant DiscoveryExplorationView oldWidget) {
    super.didUpdateWidget(oldWidget);
    final keys = widget.selection.collection.items
        .map((item) => item.candidateKey)
        .toSet();
    if (_focusedCandidateKey != null && !keys.contains(_focusedCandidateKey)) {
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
            onPage: widget.onPage,
            onRetry: widget.onRetry,
            onResetCriteria: widget.onResetCriteria,
          );
        }

        final field = DiscoveryFieldView(
          selection: widget.selection,
          onOpen: widget.onOpen,
          onPage: widget.onPage,
          onRetry: widget.onRetry,
          onResetCriteria: widget.onResetCriteria,
          selectedCandidateKey: _focusedCandidateKey,
          onSelect: (item) => setState(() {
            _focusedCandidateKey = item.candidateKey;
          }),
          selectOnCardTap: true,
        );
        if (focused == null) return field;

        return MakoloAdaptiveSplit(
          splitAt: MakoloLayout.wideMinWidth,
          field: field,
          focus: _DiscoveryFocusPane(
            item: focused,
            onClose: () => setState(() => _focusedCandidateKey = null),
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
    this.onPage,
    this.onRetry,
    this.onResetCriteria,
    this.selectedCandidateKey,
    this.onSelect,
    this.selectionActionLabel,
    this.selectOnCardTap = false,
  });

  final DiscoveryFieldSelection selection;
  final DiscoveryOpenItem onOpen;
  final ValueChanged<int>? onPage;
  final VoidCallback? onRetry;
  final VoidCallback? onResetCriteria;
  final String? selectedCandidateKey;
  final ValueChanged<DiscoveryItemPresentation>? onSelect;
  final String? selectionActionLabel;
  final bool selectOnCardTap;

  @override
  Widget build(BuildContext context) {
    return MakoloSurfaceStateView(
      state: selection.surface,
      recoverableErrorMessage: 'La mise à jour n’a pas abouti. Les possibilités connues restent disponibles.',
      blockingErrorMessage:
          'Makolo ne peut pas interpréter le champ de possibilités reçu.',
      preservedMessage: selection.collection.items.isEmpty
          ? null
          : 'Le champ déjà acquis reste consultable.',
      onRetry: onRetry,
      empty: _DiscoveryEmptyState(
        states: selection.states,
        onRetry: onRetry,
        onResetCriteria: onResetCriteria,
      ),
      content: _DiscoveryScrollableField(
        selection: selection,
        onOpen: onOpen,
        onPage: onPage,
        selectedCandidateKey: selectedCandidateKey,
        onSelect: onSelect,
        selectionActionLabel: selectionActionLabel,
        selectOnCardTap: selectOnCardTap,
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
    this.onPage,
    this.onRetry,
  });

  final DiscoveryFieldSelection selection;
  final MakoloMapsConfig mapConfig;
  final DiscoveryOpenItem onOpen;
  final ValueChanged<int>? onPage;
  final VoidCallback? onRetry;

  @override
  State<DiscoverySpatialView> createState() => _DiscoverySpatialViewState();
}

class _DiscoverySpatialViewState extends State<DiscoverySpatialView> {
  static const _selector = DiscoverySelector();
  String? _selectedCandidateKey;

  @override
  void didUpdateWidget(covariant DiscoverySpatialView oldWidget) {
    super.didUpdateWidget(oldWidget);
    final keys = widget.selection.collection.items
        .map((item) => item.candidateKey)
        .toSet();
    if (_selectedCandidateKey != null &&
        !keys.contains(_selectedCandidateKey)) {
      _selectedCandidateKey = null;
    }
  }

  DiscoveryItemPresentation? get _selectedItem {
    final items = widget.selection.collection.items;
    if (items.isEmpty) return null;
    final key = _selectedCandidateKey;
    if (key != null) {
      for (final item in items) {
        if (item.candidateKey == key) return item;
      }
    }
    for (final item in items) {
      if (item.isMappable) return item;
    }
    return items.first;
  }

  @override
  Widget build(BuildContext context) {
    final points = _selector.mapPointsFromCollection(
      widget.selection.collection,
    );
    final selected = _selectedItem;
    DiscoveryMapPoint? selectedPoint;
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
      onPage: widget.onPage,
      onRetry: widget.onRetry,
      selectedCandidateKey: _selectedCandidateKey,
      onSelect: (item) => setState(() {
        _selectedCandidateKey = item.candidateKey;
      }),
      selectionActionLabel: 'Voir sur la carte',
    );

    if (points.isEmpty) {
      return field;
    }

    final anchor = selectedPoint ?? points.first;
    final spatial = MakoloSpatialFrame(
      spatial: Stack(
        key: const Key('discover-spatial-stack'),
        children: [
          Positioned.fill(
            child: ConfiguredMakoloMapView(
              key: ValueKey(
                'discover-map-${anchor.candidateKey ?? anchor.occurrenceId}',
              ),
              config: widget.mapConfig,
              initialViewport: MapViewport(
                center: MapCoordinate(anchor.latitude, anchor.longitude),
                zoom: 11,
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
                          'La carte n’est pas disponible. Le champ reste entièrement utilisable.',
                          textAlign: TextAlign.center,
                        ),
                        if (retryable) ...[
                          const SizedBox(height: MakoloSpacing.md),
                          OutlinedButton(
                            onPressed: retry,
                            child: const Text('Réessayer la carte'),
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
      compactFallback: field,
    );

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
    this.onPage,
    this.selectedCandidateKey,
    this.onSelect,
    this.selectionActionLabel,
    this.selectOnCardTap = false,
  });

  final DiscoveryFieldSelection selection;
  final DiscoveryOpenItem onOpen;
  final ValueChanged<int>? onPage;
  final String? selectedCandidateKey;
  final ValueChanged<DiscoveryItemPresentation>? onSelect;
  final String? selectionActionLabel;
  final bool selectOnCardTap;

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

        return ListView(
          key: PageStorageKey<String>(
            'discover-page-${selection.collection.page}',
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
                  Text(
                    'Découvrir',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    'Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?',
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: MakoloSpacing.lg),
                  if (wide)
                    MakoloAdaptiveGrid(
                      key: const Key('discover-wide-grid'),
                      minUnitWidth: MakoloLayout.unitMinWidth,
                      maxColumns: 3,
                      children: units,
                    )
                  else
                    Column(
                      key: const Key('discover-compact-field'),
                      children: [
                        for (var index = 0; index < units.length; index++) ...[
                          units[index],
                          if (index < units.length - 1)
                            const SizedBox(height: MakoloSpacing.md),
                        ],
                      ],
                    ),
                  if (selection.states.contains(
                    DiscoveryFieldState.endOfField,
                  )) ...[
                    const SizedBox(height: MakoloSpacing.lg),
                    const _DiscoveryEndOfField(),
                  ],
                  if (selection.collection.page > 1 ||
                      selection.collection.hasNext) ...[
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
    this.onSelect,
    this.selectionActionLabel,
  });

  final DiscoveryItemPresentation item;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback? onSelect;
  final String? selectionActionLabel;

  bool get _hasContextualMedia =>
      item.imageUrl != null || item.routeLabel != null;

  @override
  Widget build(BuildContext context) {
    final metadata = <MakoloMetadataItem>[
      if (item.owner != null)
        MakoloMetadataItem(item.owner!, icon: Icons.business_outlined),
      if (item.place != null)
        MakoloMetadataItem(item.place!, icon: Icons.place_outlined),
      if (item.timing != null)
        MakoloMetadataItem(item.timing!, icon: Icons.schedule_outlined),
      if (item.price != null)
        MakoloMetadataItem(item.price!, icon: Icons.payments_outlined),
    ];

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
      child: MakoloCard(
        onTap: onTap,
        semanticLabel: 'Possibilité. ${item.title}',
        padding: EdgeInsets.zero,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_hasContextualMedia)
              Padding(
                padding: const EdgeInsets.all(MakoloSpacing.sm),
                child: _DiscoveryMedia(item: item),
              ),
            Padding(
              padding: const EdgeInsets.all(MakoloSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (item.eyebrow != null)
                    Text(
                      item.eyebrow!,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  if (item.eyebrow != null)
                    const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    item.title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  if (item.summary.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      item.summary,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  if (metadata.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.md),
                    MakoloMetadata(items: metadata),
                  ],
                  if (item.availability != null) ...[
                    const SizedBox(height: MakoloSpacing.md),
                    MakoloStatus(label: item.availability!),
                  ],
                  if (onSelect != null) ...[
                    const SizedBox(height: MakoloSpacing.md),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        key: ValueKey(
                          'discover-map-action-${item.candidateKey}',
                        ),
                        onPressed: onSelect,
                        icon: const Icon(Icons.map_outlined),
                        label: Text(selectionActionLabel ?? 'Sélectionner'),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DiscoveryMedia extends StatelessWidget {
  const _DiscoveryMedia({required this.item});

  final DiscoveryItemPresentation item;

  @override
  Widget build(BuildContext context) {
    final uri = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    final networkImage =
        uri != null && (uri.scheme == 'https' || uri.scheme == 'http');

    Widget? child;
    if (networkImage) {
      child = Image.network(
        item.imageUrl!,
        fit: BoxFit.cover,
        errorBuilder: (_, _, _) =>
            MakoloMediaPlaceholder(label: item.eyebrow ?? 'Média indisponible'),
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
  });

  final DiscoveryItemPresentation item;
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
            _DiscoveryMedia(item: item),
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
    if (states.contains(DiscoveryFieldState.offlineNoSnapshot)) {
      return _EmptyBody(
        icon: Icons.cloud_off_outlined,
        title:
            'Impossible de charger de nouvelles possibilités hors connexion.',
        body: 'Aucun snapshot Discovery n’est disponible sur cet appareil. Réessayez lorsque la source est joignable.',
        actionLabel: onRetry == null ? null : 'Réessayer',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.offlineWithSnapshot)) {
      return _EmptyBody(
        icon: Icons.cloud_off_outlined,
        title: 'Le champ disponible est limité à ce qui est déjà acquis.',
        body: 'Vous êtes hors connexion. Makolo ne présente pas ce corpus local comme exhaustif.',
        actionLabel: onRetry == null ? null : 'Réessayer',
        onAction: onRetry,
      );
    }
    if (states.contains(DiscoveryFieldState.noMatch)) {
      return _EmptyBody(
        icon: Icons.search_off_outlined,
        title: 'Aucune possibilité ne correspond à ces critères.',
        body: 'Modifiez la recherche, retirez une contrainte ou élargissez volontairement la zone.',
        actionLabel: onResetCriteria == null ? null : 'Modifier mes critères',
        onAction: onResetCriteria,
      );
    }
    return const _EmptyBody(
      icon: Icons.explore_outlined,
      title: 'Aucune proposition suffisante dans ce contexte pour le moment.',
      body: 'Makolo n’invente pas de contenu pour remplir Découvrir. Vous pouvez préciser ce que vous cherchez.',
    );
  }
}

class _EmptyBody extends StatelessWidget {
  const _EmptyBody({
    required this.icon,
    required this.title,
    required this.body,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String body;
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
        const SizedBox(height: MakoloSpacing.sm),
        Text(
          body,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyMedium,
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
          child: Text(
            'Vous avez parcouru ce qui est disponible dans ce contexte. Makolo n’ajoute pas de contenu de remplissage.',
            textAlign: TextAlign.center,
          ),
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
