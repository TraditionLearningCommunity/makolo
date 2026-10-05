import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_status.dart';
import 'day_of_repository.dart';
import 'day_of_selector.dart';

class DayOfScreen extends StatefulWidget {
  const DayOfScreen({
    super.key,
    required this.occurrenceId,
    required this.repository,
    required this.onOpenAccess,
    required this.onPresentCredential,
    this.onOpenLive,
  });

  final String occurrenceId;
  final DayOfRepository repository;
  final void Function(String accessId, String detailPath) onOpenAccess;
  final void Function(String accessId, String credentialPath)
  onPresentCredential;
  final void Function(String livePath)? onOpenLive;

  @override
  State<DayOfScreen> createState() => _DayOfScreenState();
}

class _DayOfScreenState extends State<DayOfScreen> with WidgetsBindingObserver {
  static const _selector = DayOfSelector();
  static const _surfaceAdapter = ProjectionSurfaceAdapter();

  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_refresh());
  }

  @override
  void didUpdateWidget(covariant DayOfScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.occurrenceId != widget.occurrenceId ||
        oldWidget.repository != widget.repository) {
      unawaited(_refresh());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_refresh());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.occurrenceId);
    } on Object {
      // SyncSource records the owner failure and preserves the last snapshot.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: widget.repository.watchDetail(widget.occurrenceId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<DayOfSourceState>(
          stream: widget.repository.watchSource(widget.occurrenceId),
          initialData: DayOfSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? DayOfSourceState.unknown;
            final presentation = _selector.select(
              projection: projection,
              source: source,
              now: DateTime.now(),
            );
            final available = presentation.available;
            final unavailableWithoutContent =
                !available &&
                (source.invalidated ||
                    source.reachability == ReachabilityState.unreachable) &&
                !_refreshing;
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
                title: const Text('Jour J'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: MakoloSurfaceStateView(
                  state: surface,
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement de l’action en cours…',
                ),
                blockingErrorMessage: 'Cette action n’est pas disponible dans votre contexte actuel.',
                onRetry: _refresh,
                content: _DayOfContent(
                  presentation: presentation,
                  remoteActionsAvailable:
                      source.reachability != ReachabilityState.unreachable &&
                      SyncStatusScope.maybeOf(context)?.state !=
                          SyncVisualState.offline &&
                      SyncStatusScope.maybeOf(context)?.state !=
                          SyncVisualState.failed,
                  onOpenAccess: widget.onOpenAccess,
                  onPresentCredential: widget.onPresentCredential,
                  onOpenLive: widget.onOpenLive,
                ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _DayOfContent extends StatelessWidget {
  const _DayOfContent({
    required this.presentation,
    required this.remoteActionsAvailable,
    required this.onOpenAccess,
    required this.onPresentCredential,
    this.onOpenLive,
  });

  final DayOfPresentation presentation;
  final bool remoteActionsAvailable;
  final void Function(String accessId, String detailPath) onOpenAccess;
  final void Function(String accessId, String credentialPath)
  onPresentCredential;
  final void Function(String livePath)? onOpenLive;

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const Key('day-of-content'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        MakoloDetailHeader(
          eyebrow: 'Jour J',
          title: presentation.title,
          subtitle: presentation.occurrenceLabel,
        ),
        if (presentation.nextLabel != null) ...[
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: MakoloAttentionBlock(
              title: 'À faire maintenant',
              body: presentation.nextLabel!,
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.destination != null) ...[
          MakoloSection(
            title: 'Où aller',
            child: _DestinationCard(destination: presentation.destination!),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.accesses.isNotEmpty) ...[
          MakoloSection(
            title: 'Accès',
            child: Column(
              children: [
                for (
                  var index = 0;
                  index < presentation.accesses.length;
                  index++
                ) ...[
                  _AccessCard(
                    access: presentation.accesses[index],
                    onOpenAccess: onOpenAccess,
                    onPresentCredential: onPresentCredential,
                  ),
                  if (index < presentation.accesses.length - 1)
                    const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.actorInterventions.isNotEmpty ||
            presentation.blockers.isNotEmpty) ...[
          MakoloSection(
            title: 'À régler',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final item in presentation.actorInterventions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: MakoloAttentionBlock(
                      title: 'Action requise',
                      body: item,
                    ),
                  ),
                for (final item in presentation.blockers)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: MakoloAttentionBlock(
                      title: 'Avant de continuer',
                      body: item,
                      icon: Icons.block_rounded,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.queue.isNotEmpty) ...[
          MakoloSection(
            title: 'File d’attente',
            child: Column(
              children: [
                for (final entry in presentation.queue)
                  MakoloCard(
                    child: Row(
                      children: [
                        const Icon(Icons.people_outline_rounded),
                        const SizedBox(width: MakoloSpacing.compact),
                        Expanded(child: Text(entry.label ?? 'File d’attente')),
                        if (entry.position != null)
                          Text('Position ${entry.position}'),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.placements.isNotEmpty) ...[
          MakoloSection(
            title: 'Placement',
            child: Column(
              children: [
                for (final placement in presentation.placements)
                  MakoloCard(
                    child: Text(
                      [
                        placement.unit,
                        placement.parentUnit,
                        placement.plan,
                      ].whereType<String>().join(' · '),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.nextCheckpoint?.label != null) ...[
          MakoloSection(
            title: 'Étape sur place',
            child: MakoloCard(child: Text(presentation.nextCheckpoint!.label!)),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.hazards.isNotEmpty) ...[
          MakoloSection(
            title: 'À savoir',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final hazard in presentation.hazards)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: MakoloAttentionBlock(
                      title: 'Information actuelle',
                      body: hazard,
                      icon: Icons.info_outline_rounded,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        if (presentation.canOpenLive && onOpenLive != null)
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                FilledButton.icon(
                  onPressed: remoteActionsAvailable
                      ? () => onOpenLive!(presentation.livePath!)
                      : null,
                  icon: const Icon(Icons.play_circle_outline_rounded),
                  label: const Text('Voir la situation en direct'),
                ),
                if (!remoteActionsAvailable) ...[
                  const SizedBox(height: MakoloSpacing.xs),
                  Text(
                    'Connexion requise',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _DestinationCard extends StatelessWidget {
  const _DestinationCard({required this.destination});

  final DayOfDestination destination;

  @override
  Widget build(BuildContext context) {
    final lines = <String>[
      if (destination.name != null) destination.name!,
      if (destination.addressLine != null) destination.addressLine!,
      if (destination.locality != null) destination.locality!,
      if (destination.accessInstructions != null)
        destination.accessInstructions!,
    ];

    return MakoloCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.place_outlined),
          const SizedBox(width: MakoloSpacing.compact),
          Expanded(child: Text(lines.join('\n'))),
        ],
      ),
    );
  }
}

class _AccessCard extends StatelessWidget {
  const _AccessCard({
    required this.access,
    required this.onOpenAccess,
    required this.onPresentCredential,
  });

  final DayOfAccessPresentation access;
  final void Function(String accessId, String detailPath) onOpenAccess;
  final void Function(String accessId, String credentialPath)
  onPresentCredential;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      semanticLabel: 'Accès',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            access.usable ? 'Prêt à présenter' : 'Accès à vérifier',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (access.canPresentCredential) ...[
            const SizedBox(height: MakoloSpacing.md),
            FilledButton.icon(
              onPressed: () =>
                  onPresentCredential(access.id, access.credentialPath!),
              icon: const Icon(Icons.qr_code_2_rounded),
              label: const Text('Afficher le QR'),
            ),
          ],
          if (access.canOpenAccess) ...[
            const SizedBox(height: MakoloSpacing.sm),
            OutlinedButton(
              onPressed: () => onOpenAccess(access.id, access.detailPath!),
              child: const Text('Voir l’accès'),
            ),
          ],
        ],
      ),
    );
  }
}
