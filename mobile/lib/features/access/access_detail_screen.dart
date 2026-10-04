import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import 'access_repository.dart';
import 'access_selector.dart';

class AccessDetailScreen extends StatefulWidget {
  const AccessDetailScreen({
    super.key,
    required this.accessId,
    required this.repository,
    required this.onOpenDayOf,
    this.onOpenJourney,
    this.onOpenPresentation,
  });

  final String accessId;
  final AccessRepository repository;
  final void Function(DayOfHandoff handoff) onOpenDayOf;
  final void Function(String journeyId)? onOpenJourney;
  final VoidCallback? onOpenPresentation;

  @override
  State<AccessDetailScreen> createState() => _AccessDetailScreenState();
}

class _AccessDetailScreenState extends State<AccessDetailScreen> {
  static const _selector = AccessDetailSelector();
  static const _surfaceAdapter = ProjectionSurfaceAdapter();

  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  @override
  void didUpdateWidget(covariant AccessDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.accessId != widget.accessId ||
        oldWidget.repository != widget.repository) {
      unawaited(_refresh());
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.accessId);
    } on Object {
      // SyncSource records the owner failure and preserves usable local data.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: widget.repository.watchDetail(widget.accessId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<AccessSourceState>(
          stream: widget.repository.watchSource(widget.accessId),
          initialData: AccessSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? AccessSourceState.unknown;
            final presentation = _selector.select(
              projection: projection,
              source: source,
              now: DateTime.now(),
            );
            final available = presentation.available;
            final unavailableWithoutContent =
                !available && source.invalidated && !_refreshing;
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: presentation.freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: unavailableWithoutContent
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );

            return Scaffold(
              appBar: AppBar(
                title: const Text('Accès'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloSurfaceStateView(
                state: surface,
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement de l’accès…',
                ),
                blockingErrorMessage: 'Cet accès n’est pas disponible dans votre contexte actuel.',
                preservedMessage: 'Aucune copie locale utilisable n’est disponible sur cet appareil.',
                onRetry: _refresh,
                content: _AccessContent(
                  presentation: presentation,
                  onOpenDayOf: widget.onOpenDayOf,
                  onOpenJourney: widget.onOpenJourney,
                  onOpenPresentation: widget.onOpenPresentation,
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _AccessContent extends StatelessWidget {
  const _AccessContent({
    required this.presentation,
    required this.onOpenDayOf,
    this.onOpenJourney,
    this.onOpenPresentation,
  });

  final AccessDetailPresentation presentation;
  final void Function(DayOfHandoff handoff) onOpenDayOf;
  final void Function(String journeyId)? onOpenJourney;
  final VoidCallback? onOpenPresentation;

  @override
  Widget build(BuildContext context) {
    final metadata = <MakoloMetadataItem>[
      if (presentation.validFrom != null)
        MakoloMetadataItem(
          'Valable à partir du ${_formatDateTime(context, presentation.validFrom!)}',
          icon: Icons.schedule_rounded,
        ),
      if (presentation.validUntil != null)
        MakoloMetadataItem(
          'Valable jusqu’au ${_formatDateTime(context, presentation.validUntil!)}',
          icon: Icons.event_available_rounded,
        ),
      if (presentation.singleUse)
        const MakoloMetadataItem(
          'Usage unique',
          icon: Icons.looks_one_outlined,
        ),
    ];

    final relationshipCopy = presentation.relationship == 'purchased_for_other'
        ? 'Vous avez obtenu cet accès pour une autre personne.'
        : 'Cet accès vous concerne directement.';

    return ListView(
      key: const Key('access-detail-content'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        MakoloDetailHeader(
          eyebrow: 'Accès',
          title: presentation.activityTitle,
          subtitle: relationshipCopy,
          metadata: metadata,
        ),
        if (onOpenPresentation != null) ...[
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: FilledButton.tonalIcon(
              onPressed: onOpenPresentation,
              icon: const Icon(Icons.auto_awesome_mosaic_outlined),
              label: const Text('Voir la présentation'),
            ),
          ),
          const SizedBox(height: MakoloSpacing.lg),
        ],
        if (presentation.canOpenDayOf) ...[
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: MakoloAttentionBlock(
              title: 'Action réelle',
              body: 'Les informations utiles pour le moment venu sont disponibles.',
              action: FilledButton.icon(
                onPressed: () => onOpenDayOf(presentation.dayOf!),
                icon: const Icon(Icons.directions_walk_rounded),
                label: const Text('Ouvrir l’action en cours'),
              ),
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.journeyId != null && onOpenJourney != null)
          MakoloSection(
            title: 'Démarche liée',
            child: MakoloCard(
              semanticLabel: 'Voir la démarche liée',
              onTap: () => onOpenJourney!(presentation.journeyId!),
              child: const Row(
                children: [
                  Icon(Icons.route_rounded),
                  SizedBox(width: MakoloSpacing.compact),
                  Expanded(child: Text('Voir la démarche')),
                  Icon(Icons.chevron_right_rounded),
                ],
              ),
            ),
          ),
      ],
    );
  }

  static String _formatDateTime(BuildContext context, DateTime value) {
    final local = value.toLocal();
    final localizations = MaterialLocalizations.of(context);
    return '${localizations.formatShortDate(local)} · '
        '${localizations.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
  }
}
