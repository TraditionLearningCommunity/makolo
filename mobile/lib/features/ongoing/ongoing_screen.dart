import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/refresh_boundary.dart';
import '../../presentation/humanization.dart';
import '../../repositories/personal_repository.dart';
import 'ongoing_presentation.dart';

class OngoingScreen extends StatefulWidget {
  const OngoingScreen({
    super.key,
    required this.repository,
    this.projectionStream,
  });
  final PersonalRepository repository;
  final Stream<StoredProjection?>? projectionStream;
  @override
  State<OngoingScreen> createState() => _OngoingScreenState();
}

class _OngoingScreenState extends State<OngoingScreen> {
  String? _selectedOwnerKey;
  StoredProjection? _lastProjection;

  void _select(OngoingContinuityPresentation item) =>
      setState(() => _selectedOwnerKey = _ownerKey(item));
  void _clearSelection() => setState(() => _selectedOwnerKey = null);

  String _ownerKey(OngoingContinuityPresentation item) =>
      '${item.ownerKind ?? item.kind}:${item.ownerId ?? item.title}';

  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: StreamBuilder<StoredProjection?>(
      stream: widget.projectionStream ?? widget.repository.watchOngoing(),
      builder: (context, snapshot) {
        if (snapshot.hasData && snapshot.data != null) {
          _lastProjection = snapshot.data;
        }
        final projection = snapshot.data ?? _lastProjection;
        if (!snapshot.hasData &&
            snapshot.connectionState == ConnectionState.waiting) {
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
            empty: MakoloEmptyState(title: 'Rien en cours pour le moment.'),
            content: SizedBox.shrink(),
          );
        }
        final items = OngoingContinuityPresentation.fromProjection(projection);
        if (items.isEmpty) {
          return const MakoloSurfaceStateView(
            state: MakoloSurfacePresentation(
              availability: MakoloAvailabilityCue.empty,
            ),
            empty: MakoloEmptyState(title: 'Rien en cours pour le moment.'),
            content: SizedBox.shrink(),
          );
        }
        final matches = items.where(
          (item) => _ownerKey(item) == _selectedOwnerKey,
        );
        final selected = matches.isEmpty ? null : matches.first;
        final stale =
            projection.freshUntil != null &&
            projection.freshUntil!.isBefore(DateTime.now().toUtc());
        return MakoloSurfaceStateView(
          state: MakoloSurfacePresentation(
            availability: MakoloAvailabilityCue.content,
            freshness: stale
                ? MakoloFreshnessCue.oldObservation
                : MakoloFreshnessCue.current,
            failure: snapshot.hasError
                ? MakoloFailureCue.recoverable
                : MakoloFailureCue.none,
          ),
          content: _OngoingAdaptiveView(
            items: items,
            selected: selected,
            stale: stale,
            onSelect: _select,
            onBack: _clearSelection,
          ),
          recoverableErrorMessage: 'La mise à jour a échoué. Le contenu déjà disponible reste utilisable.',
        );
      },
    ),
  );
}

class _OngoingAdaptiveView extends StatelessWidget {
  const _OngoingAdaptiveView({
    required this.items,
    required this.selected,
    required this.stale,
    required this.onSelect,
    required this.onBack,
  });
  final List<OngoingContinuityPresentation> items;
  final OngoingContinuityPresentation? selected;
  final bool stale;
  final ValueChanged<OngoingContinuityPresentation> onSelect;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) => MakoloContentFrame(
    maxContentWidth: 1040,
    child: MakoloAdaptiveSplit(
      splitAt: MakoloLayout.ongoingSplitMinWidth,
      field: _OngoingField(
        items: items,
        selected: selected,
        stale: stale,
        onSelect: onSelect,
      ),
      focus: selected == null
          ? const _OngoingFocusPlaceholder()
          : _OngoingFocus(item: selected!, onBack: onBack),
      narrow: selected == null
          ? _OngoingField(
              items: items,
              selected: selected,
              stale: stale,
              onSelect: onSelect,
            )
          : _OngoingFocus(item: selected!, onBack: onBack),
    ),
  );
}

class _OngoingField extends StatelessWidget {
  const _OngoingField({
    required this.items,
    required this.selected,
    required this.stale,
    required this.onSelect,
  });
  final List<OngoingContinuityPresentation> items;
  final OngoingContinuityPresentation? selected;
  final bool stale;
  final ValueChanged<OngoingContinuityPresentation> onSelect;

  @override
  Widget build(BuildContext context) => ListView.separated(
    key: const PageStorageKey<String>('ongoing-field'),
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
    itemCount: items.length,
    separatorBuilder: (_, _) => const SizedBox(height: MakoloSpacing.lg),
    itemBuilder: (context, index) {
      final item = items[index];
      final key =
          '${item.ownerKind ?? item.kind}:${item.ownerId ?? item.title}';
      final selectedKey = selected == null
          ? null
          : '${selected!.ownerKind ?? selected!.kind}:${selected!.ownerId ?? selected!.title}';
      return _OngoingRow(
        item: item,
        selected: key == selectedKey,
        stale: stale,
        onTap: () => onSelect(item),
      );
    },
  );
}

class _OngoingRow extends StatelessWidget {
  const _OngoingRow({
    required this.item,
    required this.selected,
    required this.stale,
    required this.onTap,
  });
  final OngoingContinuityPresentation item;
  final bool selected;
  final bool stale;
  final VoidCallback onTap;

  String? _supportingLine(OngoingContinuityPresentation item) {
    final candidate = item.mySide.isNotEmpty
        ? item.mySide.first
        : item.next.isNotEmpty
        ? item.next.first
        : null;
    return candidate == null || candidate == item.synthesis ? null : candidate;
  }

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    selected: selected,
    label: '${item.title}. ${item.synthesis}',
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(MakoloRadii.card),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(item.title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: MakoloSpacing.sm),
            Text(item.synthesis, style: Theme.of(context).textTheme.bodyLarge),
            if (_supportingLine(item) != null) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                _supportingLine(item)!,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
            if (stale) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                'Dernière information connue',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    ),
  );
}

class _OngoingFocusPlaceholder extends StatelessWidget {
  const _OngoingFocusPlaceholder();
  @override
  Widget build(BuildContext context) => const MakoloFocusPane(
    child: Padding(
      padding: EdgeInsets.all(MakoloSpacing.lg),
      child: Text('Sélectionnez une continuité pour voir ce qui continue.'),
    ),
  );
}

class _OngoingFocus extends StatelessWidget {
  const _OngoingFocus({required this.item, required this.onBack});

  final OngoingContinuityPresentation item;
  final VoidCallback onBack;

  bool get _hasStructuredDetail =>
      item.settled.isNotEmpty ||
      item.mySide.isNotEmpty ||
      item.elsewhere.isNotEmpty ||
      item.next.isNotEmpty ||
      item.waiting != null ||
      item.blocker != null ||
      item.unknown != null;

  List<Widget> _detailSections() {
    final seen = <String>{};
    List<String> unique(Iterable<String> values) => [
      for (final value in values)
        if (value.trim().isNotEmpty && seen.add(value.trim())) value.trim(),
    ];

    final sections = <Widget>[];
    void add(String title, Iterable<String> values) {
      final visible = unique(values);
      if (visible.isNotEmpty) {
        sections.add(_DimensionSection(title: title, values: visible));
      }
    }

    add('Déjà réglé', item.settled);
    add('De votre côté', item.mySide);
    add('Ailleurs', item.elsewhere);
    add('Ensuite', item.next);
    if (item.waiting != null) add('En attente', [item.waiting!]);
    if (item.blocker != null) add('Ce qui bloque', [item.blocker!]);
    if (item.unknown != null) add('À vérifier', [item.unknown!]);
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

  @override
  Widget build(BuildContext context) {
    final showBack =
        MediaQuery.sizeOf(context).width < MakoloLayout.ongoingSplitMinWidth;
    final metadata = _humanMetadata();
    return SingleChildScrollView(
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
            if (!_hasStructuredDetail) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(item.synthesis, style: Theme.of(context).textTheme.bodyLarge),
            ],
            ..._detailSections(),
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
  const _DimensionSection({required this.title, required this.values});
  final String title;
  final List<String> values;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: MakoloSpacing.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: MakoloSpacing.sm),
        for (final value in values) ...[
          Text(value, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: MakoloSpacing.xs),
        ],
      ],
    ),
  );
}
