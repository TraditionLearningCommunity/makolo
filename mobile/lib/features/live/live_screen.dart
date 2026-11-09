import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../sync/sync_status.dart';
import '../occurrence/occurrence_continuity.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../data/local/profile_store.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../occurrence/occurrence_experience_content.dart';
import 'live_repository.dart';

class LiveScreen extends StatefulWidget {
  const LiveScreen({
    super.key,
    required this.occurrenceId,
    required this.repository,
    this.actorContext,
    this.onBackToDayOf,
    this.onOpenDepth,
  });

  final String occurrenceId;
  final LiveRepository repository;
  final ActorContextController? actorContext;
  final VoidCallback? onBackToDayOf;
  final ValueChanged<String>? onOpenDepth;

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> with WidgetsBindingObserver {
  bool refreshing = false;
  int _revision = 0;
  DateTime? _actorSwitchedAt;
  Timer? _reconciliationTimer;

  bool get _actorValid =>
      widget.actorContext == null ||
      widget.actorContext!.value is! SpaceActorContext;

  void _onActorChanged() {
    _actorSwitchedAt = DateTime.now().toUtc();
    _revision++;
    if (!mounted) return;
    setState(() => refreshing = false);
    if (_actorValid) unawaited(_refresh());
  }

  void _startReconciliation() {
    _reconciliationTimer?.cancel();
    _reconciliationTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!mounted || !_actorValid) return;
      setState(() {});
      unawaited(_refresh());
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.actorContext?.addListener(_onActorChanged);
    _startReconciliation();
    unawaited(_refresh());
  }

  @override
  void didUpdateWidget(covariant LiveScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.actorContext != widget.actorContext) {
      oldWidget.actorContext?.removeListener(_onActorChanged);
      widget.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.occurrenceId != widget.occurrenceId ||
        oldWidget.repository != widget.repository ||
        oldWidget.actorContext != widget.actorContext) {
      _onActorChanged();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _startReconciliation();
      unawaited(_refresh());
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _reconciliationTimer?.cancel();
    }
  }

  @override
  void dispose() {
    _revision++;
    _reconciliationTimer?.cancel();
    widget.actorContext?.removeListener(_onActorChanged);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> _refresh() async {
    if (refreshing || !_actorValid) return;
    final revision = ++_revision;
    final repository = widget.repository;
    final id = widget.occurrenceId;
    setState(() => refreshing = true);
    try {
      await repository.refresh(id);
    } on Object {
      // The source separates owner refusal from transport unavailability.
    } finally {
      if (mounted && _actorValid && _revision == revision) {
        setState(() => refreshing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => StreamBuilder<StoredProjection?>(
    stream: widget.repository.watch(widget.occurrenceId),
    builder: (context, projectionSnapshot) => StreamBuilder<LiveSourceState>(
      stream: widget.repository.watchSource(widget.occurrenceId),
      initialData: LiveSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final source = sourceSnapshot.data ?? LiveSourceState.unknown;
        final projection = projectionSnapshot.data;
        final base = projection == null
            ? null
            : const ProjectionSelector().select(
                projection: projection,
                freshnessPolicy: LiveRepository.freshnessPolicy,
                now: DateTime.now(),
                sourceInvalidated: source.invalidated,
              );
        final scoped =
            _actorValid &&
            projection != null &&
            OccurrenceContinuity.matches(
              payload: projection.payload,
              occurrenceId: widget.occurrenceId,
              profileId: widget.repository.profileId,
              surface: 'live',
            );
        final available =
            scoped &&
            !source.invalidated &&
            OccurrenceContinuity.verifiedAfterActorSwitch(
              lastSuccessAt: source.lastSuccessAt,
              actorSwitchedAt: _actorSwitchedAt,
            );
        final liveEnded =
            scoped &&
            OccurrenceContinuity.liveWindowEnded(
              projection.payload,
              now: DateTime.now(),
            );
        final globalState = SyncStatusScope.maybeOf(context)?.state;
        final offline =
            globalState == SyncVisualState.offline ||
            globalState == SyncVisualState.failed ||
            globalState == SyncVisualState.conflict ||
            globalState == SyncVisualState.stale;
        final actionsAllowed = OccurrenceContinuity.canOfferActions(
          sourceInvalidated: source.invalidated,
          reachability: source.reachability,
          freshness: base?.freshness,
          systemOffline: offline,
          liveEnded: liveEnded,
        );
        final readOnlyReason = liveEnded
            ? 'La fenêtre Live est terminée. Ces informations ne sont pas du direct.'
            : actionsAllowed
            ? null
            : source.reachability != ReachabilityState.reachable || offline
            ? 'Dernière situation connue. Source actuellement inaccessible.'
            : 'Situation ancienne, réconciliation requise.';
        final unavailable =
            !available &&
            !refreshing &&
            source.reachability == ReachabilityState.unreachable;
        final surface = const ProjectionSurfaceAdapter().adapt(
          projection: ProjectionPresentationModel(
            available: available,
            payload: projection?.payload,
            freshness: base?.freshness,
            resources: const [],
            drafts: const [],
            pendingOperations: const [],
          ),
          availability: available
              ? MakoloAvailabilityCue.content
              : refreshing
              ? MakoloAvailabilityCue.loading
              : MakoloAvailabilityCue.initial,
          reachability: source.reachability,
          failure: unavailable
              ? MakoloFailureCue.blocking
              : MakoloFailureCue.none,
          refreshing: refreshing && available,
        );
        return Scaffold(
          appBar: AppBar(
            title: const Text('Makolo Live'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: MakoloNetworkContextFrame(
            child: MakoloSurfaceStateView(
              state: surface,
              initialLoading: const MakoloLoadingState(
                label: 'Actualisation de la situation…',
              ),
              blockingErrorMessage: source.invalidated
                  ? 'Cette Occurrence n’est plus dans sa fenêtre Live. Retrouvez ses conséquences dans Jour J et Historique.'
                  : 'Makolo Live n’est pas activé ou accessible pour cette Occurrence. Jour J reste disponible.',
              onRetry: _refresh,
              content: available && projection.payload['surface'] == 'live'
                  ? OccurrenceExperienceContent(
                      payload: projection.payload,
                      live: true,
                      remoteActionsAvailable: actionsAllowed,
                      liveWindowEnded: liveEnded,
                      readOnlyReason: readOnlyReason,
                      lastKnownAt: source.lastSuccessAt,
                      onBackToDayOf: widget.onBackToDayOf,
                      onOpenDepth: widget.onOpenDepth,
                    )
                  : const SizedBox.shrink(),
            ),
          ),
        );
      },
    ),
  );
}
