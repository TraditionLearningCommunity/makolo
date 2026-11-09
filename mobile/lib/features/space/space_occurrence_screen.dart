import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../sync/sync_status.dart';
import '../occurrence/occurrence_continuity.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../occurrence/occurrence_experience_content.dart';
import 'space_occurrence_repository.dart';

class SpaceOccurrenceScreen extends StatefulWidget {
  const SpaceOccurrenceScreen({
    super.key,
    required this.space,
    required this.occurrenceId,
    required this.repository,
    this.actorContext,
    required this.live,
    this.onOpenLive,
    this.onOpenScanner,
    this.onOpenAccess,
    this.onPresentCredential,
    this.onBackToDayOf,
    this.onOpenDepth,
    this.onOpenHistory,
  });

  final SpaceActorIdentity space;
  final String occurrenceId;
  final SpaceOccurrenceRepository repository;
  final ActorContextController? actorContext;
  final bool live;
  final VoidCallback? onOpenLive;
  final VoidCallback? onOpenScanner;
  final void Function(String accessId, String path)? onOpenAccess;
  final void Function(String accessId, String path)? onPresentCredential;
  final VoidCallback? onBackToDayOf;
  final ValueChanged<String>? onOpenDepth;
  final VoidCallback? onOpenHistory;

  @override
  State<SpaceOccurrenceScreen> createState() => _SpaceOccurrenceScreenState();
}

class _SpaceOccurrenceScreenState extends State<SpaceOccurrenceScreen>
    with WidgetsBindingObserver {
  bool refreshing = false;
  int _revision = 0;
  DateTime? _actorSwitchedAt;
  Timer? _reconciliationTimer;

  bool get _actorValid =>
      widget.actorContext == null ||
      (widget.actorContext!.value is SpaceActorContext &&
          (widget.actorContext!.value as SpaceActorContext).space ==
              widget.space);

  void _onActorChanged() {
    _actorSwitchedAt = DateTime.now().toUtc();
    _revision++;
    if (!mounted) return;
    setState(() => refreshing = false);
    if (_actorValid) unawaited(_refresh());
  }

  void _startReconciliation() {
    _reconciliationTimer?.cancel();
    _reconciliationTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      if (!mounted || !_actorValid) return;
      setState(() {});
      if (widget.live || timer.tick.isEven) unawaited(_refresh());
    });
  }

  SpaceOccurrenceSourceState get unknown => SpaceOccurrenceSourceState.unknown;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.actorContext?.addListener(_onActorChanged);
    _startReconciliation();
    unawaited(_refresh());
  }

  @override
  void didUpdateWidget(covariant SpaceOccurrenceScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.actorContext != widget.actorContext) {
      oldWidget.actorContext?.removeListener(_onActorChanged);
      widget.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.space != widget.space ||
        oldWidget.occurrenceId != widget.occurrenceId ||
        oldWidget.repository != widget.repository ||
        oldWidget.live != widget.live ||
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
    final space = widget.space;
    final occurrenceId = widget.occurrenceId;
    final live = widget.live;
    setState(() => refreshing = true);
    try {
      if (live) {
        await repository.refreshLive(space, occurrenceId);
      } else {
        await repository.refreshDayOf(space, occurrenceId);
      }
    } on Object {
      // The owner source distinguishes access withdrawn from a timeout.
    } finally {
      if (mounted && _actorValid && revision == _revision) {
        setState(() => refreshing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final source = widget.live
        ? widget.repository.liveSource(widget.space, widget.occurrenceId)
        : widget.repository.dayOfSource(widget.space, widget.occurrenceId);
    final stream = widget.live
        ? widget.repository.watchLive(widget.space, widget.occurrenceId)
        : widget.repository.watchDayOf(widget.space, widget.occurrenceId);
    return StreamBuilder<StoredProjection?>(
      stream: stream,
      builder: (context, snapshot) => StreamBuilder<SpaceOccurrenceSourceState>(
        stream: widget.repository.watchSource(source),
        initialData: SpaceOccurrenceSourceState.unknown,
        builder: (context, sourceSnapshot) {
          final state = sourceSnapshot.data ?? unknown;
          final projection = snapshot.data;
          final selected = projection == null
              ? null
              : const ProjectionSelector().select(
                  projection: projection,
                  freshnessPolicy: SpaceOccurrenceRepository.freshnessPolicy,
                  now: DateTime.now(),
                  sourceInvalidated: state.invalidated,
                );
          final scoped =
              _actorValid &&
              projection != null &&
              OccurrenceContinuity.matches(
                payload: projection.payload,
                occurrenceId: widget.occurrenceId,
                profileId: widget.repository.profileId,
                actorSpaceId: widget.space.id,
                surface: widget.live ? 'live' : 'day_of',
              );
          final available =
              scoped &&
              !state.invalidated &&
              OccurrenceContinuity.verifiedAfterActorSwitch(
                lastSuccessAt: state.lastSuccessAt,
                actorSwitchedAt: _actorSwitchedAt,
              );
          final liveEnded =
              scoped &&
              OccurrenceContinuity.liveWindowEnded(
                projection.payload,
                now: DateTime.now(),
              );
          final syncVisual = SyncStatusScope.maybeOf(context)?.state;
          final offline =
              syncVisual == SyncVisualState.offline ||
              syncVisual == SyncVisualState.failed ||
              syncVisual == SyncVisualState.conflict ||
              syncVisual == SyncVisualState.stale;
          final actionsAllowed = OccurrenceContinuity.canOfferActions(
            sourceInvalidated: state.invalidated,
            reachability: state.reachability,
            freshness: selected?.freshness,
            systemOffline: offline,
            liveEnded: widget.live && liveEnded,
          );
          final readOnlyReason = liveEnded
              ? 'La fenêtre Live est terminée : dernière situation connue, pas du direct.'
              : actionsAllowed
              ? null
              : state.reachability != ReachabilityState.reachable || offline
              ? 'Réseau ou propriétaire indisponible : dernière situation connue.'
              : 'Situation ancienne : actualisez pour agir.';
          final surface = const ProjectionSurfaceAdapter().adapt(
            projection: ProjectionPresentationModel(
              available: available,
              payload: projection?.payload,
              freshness: selected?.freshness,
              resources: const [],
              drafts: const [],
              pendingOperations: const [],
            ),
            availability: available
                ? MakoloAvailabilityCue.content
                : refreshing
                ? MakoloAvailabilityCue.loading
                : MakoloAvailabilityCue.initial,
            reachability: state.reachability,
            failure: !available && state.lastErrorCode != null
                ? MakoloFailureCue.blocking
                : MakoloFailureCue.none,
            refreshing: refreshing && available,
          );
          return Scaffold(
            appBar: AppBar(
              title: Text(widget.live ? 'Live' : 'Jour J'),
              actions: [
                MakoloIconActionButton(
                  tooltip: 'Actualiser',
                  onPressed: refreshing ? null : _refresh,
                  icon: Icons.refresh_rounded,
                ),
              ],
            ),
            body: MakoloNetworkContextFrame(
              child: MakoloSurfaceStateView(
                state: surface,
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement de cette réalisation…',
                ),
                blockingErrorMessage: state.invalidated
                    ? 'Vous ne pouvez plus consulter cette réalisation dans le contexte actuel.'
                    : 'Vous n’avez pas accès à cette réalisation dans cet Espace.',
                onRetry: _refresh,
                content:
                    available &&
                        projection.payload['surface'] ==
                            (widget.live ? 'live' : 'day_of')
                    ? OccurrenceExperienceContent(
                        payload: projection.payload,
                        live: widget.live,
                        remoteActionsAvailable: actionsAllowed,
                        liveWindowEnded: liveEnded,
                        readOnlyReason: readOnlyReason,
                        lastKnownAt: state.lastSuccessAt,
                        onOpenLive: widget.onOpenLive == null
                            ? null
                            : (_) => widget.onOpenLive!(),
                        onOpenScanner: widget.onOpenScanner,
                        onOpenAccess: widget.onOpenAccess,
                        onPresentCredential: widget.onPresentCredential,
                        onBackToDayOf: widget.onBackToDayOf,
                        onOpenDepth: widget.onOpenDepth,
                        onOpenHistory: widget.onOpenHistory,
                      )
                    : const SizedBox.shrink(),
              ),
            ),
          );
        },
      ),
    );
  }
}
