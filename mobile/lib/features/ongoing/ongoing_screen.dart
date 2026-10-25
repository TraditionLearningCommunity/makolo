import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
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
  late Stream<StoredProjection?> _projectionStream;
  late Stream<OwnerSourceState> _sourceStream;

  @override
  void initState() {
    super.initState();
    _bindStreams();
  }

  @override
  void didUpdateWidget(covariant OngoingScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.projectionStream != widget.projectionStream) {
      _lastProjection = null;
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

  String _ownerKey(OngoingContinuityPresentation item) =>
      '${item.ownerKind ?? item.kind}:${item.ownerId ?? item.title}';

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
                body: 'Connectez-vous pour consulter vos démarches.',
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
              recoverableErrorMessage:
                  'Actualisation impossible.',
              preservedMessage: '',
              onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
              empty: const MakoloEmptyState(
                title: 'Aucune démarche en cours.',
              ),
              content: const SizedBox.shrink(),
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
              failure:
                  snapshot.hasError ||
                      sourceSnapshot.data?.lastErrorCode != null
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
            ),
            // Keep existing journeys visible without an additional banner.
            recoverableErrorMessage: null,
            preservedMessage:
                '',
            onRetry: () => SyncRefreshScope.maybeOf(context)?.refresh(),
            content: _OngoingAdaptiveView(
              items: items,
              selected: selected,
              stale: stale,
              onSelect: _select,
              onBack: _clearSelection,
            ),
          );
        },
      ),
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
    if (candidate == null || _ongoingRedundant(candidate, item)) return null;
    return candidate;
  }

  @override
  Widget build(BuildContext context) {
    final summary = _ongoingSummary(item.title, item.synthesis);
    final supporting = _supportingLine(item);
    final hasBlocker = item.blocker != null;
    final hasMySide = item.mySide.isNotEmpty;
    return Semantics(
      button: true,
      selected: selected,
      label: [item.title, ?summary, ?supporting].join('. '),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(item.title, style: Theme.of(context).textTheme.titleLarge),
              if (summary != null) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(summary, style: Theme.of(context).textTheme.bodyLarge),
              ],
              if (supporting != null) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(supporting, style: Theme.of(context).textTheme.bodyMedium),
              ],
              if (hasBlocker || hasMySide) ...[
                const SizedBox(height: MakoloSpacing.sm),
                MakoloStatus(
                  label: hasBlocker ? 'Bloqué' : 'Action de votre côté',
                  tone: hasBlocker
                      ? MakoloStatusTone.warning
                      : MakoloStatusTone.neutral,
                  icon: hasBlocker
                      ? Icons.block_outlined
                      : Icons.person_outline_rounded,
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
              Text(
                item.synthesis,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ],
            ..._detailSections(context),
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
