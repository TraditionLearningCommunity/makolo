import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import 'space_occurrence_repository.dart';

class SpaceOccurrenceScreen extends StatefulWidget {
  const SpaceOccurrenceScreen({
    super.key,
    required this.space,
    required this.occurrenceId,
    required this.repository,
    required this.live,
    this.onOpenLive,
    this.onOpenScanner,
    this.onBackToDayOf,
  });

  final SpaceActorIdentity space;
  final String occurrenceId;
  final SpaceOccurrenceRepository repository;
  final bool live;
  final VoidCallback? onOpenLive;
  final VoidCallback? onOpenScanner;
  final VoidCallback? onBackToDayOf;

  @override
  State<SpaceOccurrenceScreen> createState() => _SpaceOccurrenceScreenState();
}

class _SpaceOccurrenceScreenState extends State<SpaceOccurrenceScreen>
    with WidgetsBindingObserver {
  bool refreshing = false;

  SpaceOccurrenceSourceState get unknown => SpaceOccurrenceSourceState.unknown;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_refresh());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_refresh());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> _refresh() async {
    if (refreshing) return;
    setState(() => refreshing = true);
    try {
      if (widget.live) {
        await widget.repository.refreshLive(widget.space, widget.occurrenceId);
      } else {
        await widget.repository.refreshDayOf(widget.space, widget.occurrenceId);
      }
    } on Object {
      // The sync owner keeps the last viewer-scoped snapshot and failure code.
    } finally {
      if (mounted) setState(() => refreshing = false);
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
          final available = selected != null;
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
              title: Text(widget.live ? 'Live Space' : 'Jour J Space'),
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
                  label: 'Chargement de l’Occurrence opérée…',
                ),
                blockingErrorMessage: state.invalidated
                    ? 'Cette Occurrence n’est plus disponible dans cette fenêtre opératoire ou cette autorité Space.'
                    : 'Cette Occurrence n’est pas disponible dans votre autorité Space.',
                onRetry: _refresh,
                content: _SpaceOccurrenceContent(
                  payload: projection?.payload,
                  freshness: selected?.freshness,
                  live: widget.live,
                  onOpenLive: widget.onOpenLive,
                  onOpenScanner: widget.onOpenScanner,
                  onBackToDayOf: widget.onBackToDayOf,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _SpaceOccurrenceContent extends StatelessWidget {
  const _SpaceOccurrenceContent({
    required this.payload,
    required this.freshness,
    required this.live,
    this.onOpenLive,
    this.onOpenScanner,
    this.onBackToDayOf,
  });

  final Map<String, dynamic>? payload;
  final FreshnessState? freshness;
  final bool live;
  final VoidCallback? onOpenLive;
  final VoidCallback? onOpenScanner;
  final VoidCallback? onBackToDayOf;

  @override
  Widget build(BuildContext context) {
    final data = payload ?? const <String, dynamic>{};
    final contextData = _map(data['context']);
    final occurrence = _map(data['occurrence']);
    final space = _map(contextData['space']);
    final phase = _text(contextData['phase']) ?? _text(data['phase']);
    final readiness = _map(data['readiness'] ?? data['operational_readiness']);
    final capacity = _list(data['capacity']);
    final queues = _list(data['queues'] ?? data['queue']);
    final placement = _list(data['placement']);
    final scanner = _map(data['scanner']);
    final capabilities = _strings(data['capabilities']);
    return ListView(
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        if (live && onBackToDayOf != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: onBackToDayOf,
              icon: const Icon(Icons.arrow_back_rounded),
              label: const Text('Retour au Jour J Space'),
            ),
          ),
        Text(
          _text(occurrence['label']) ?? 'Occurrence opérée',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        Text(
          '${_text(space['name']) ?? 'Space'} · ${_text(_map(contextData['activity'])['title']) ?? ''}',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: MakoloSpacing.sm),
        Text(
          live
              ? _liveLabel(phase)
              : 'Jour J opérateur · ${phase ?? 'contexte actuel'}',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (freshness == FreshnessState.usableButOld ||
            freshness == FreshnessState.refreshRecommended)
          const Padding(
            padding: EdgeInsets.only(top: MakoloSpacing.sm),
            child: MakoloAttentionBlock(
              title: 'Dernière information connue',
              body: 'Actualisez pour confirmer l’état opérationnel actuel.',
              icon: Icons.schedule_rounded,
            ),
          ),
        const SizedBox(height: MakoloSpacing.lg),
        MakoloSection(
          title: 'Priorité opérationnelle',
          child: MakoloCard(
            child: Text(
              _text(_map(data['next_action'])['label']) ??
                  'Aucune action corrective confirmée maintenant.',
            ),
          ),
        ),
        const SizedBox(height: MakoloSpacing.lg),
        MakoloSection(
          title: 'Faits de cette Occurrence',
          child: MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Capacité : ${capacity.length} élément${capacity.length == 1 ? '' : 's'}',
                ),
                Text(
                  'Queue Live : ${queues.length} élément${queues.length == 1 ? '' : 's'}',
                ),
                Text(
                  'Placement : ${placement.length} attribution${placement.length == 1 ? '' : 's'}',
                ),
                Text('Readiness : ${_text(readiness['state']) ?? 'unknown'}'),
                if (scanner.isNotEmpty)
                  Text(
                    'Scanner : ${_text(scanner['state']) ?? 'disponibilité à confirmer'}',
                  ),
              ],
            ),
          ),
        ),
        if (!live &&
            capabilities.contains('open_live') &&
            onOpenLive != null) ...[
          const SizedBox(height: MakoloSpacing.lg),
          FilledButton.icon(
            onPressed: onOpenLive,
            icon: const Icon(Icons.play_circle_outline_rounded),
            label: const Text('Ouvrir Makolo Live'),
          ),
        ],
        if (!live &&
            capabilities.contains('open_scanner') &&
            onOpenScanner != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          OutlinedButton.icon(
            onPressed: onOpenScanner,
            icon: const Icon(Icons.qr_code_scanner_rounded),
            label: const Text('Ouvrir le Scanner'),
          ),
        ],
      ],
    );
  }

  static Map<String, dynamic> _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : const {};
  static List<Object?> _list(Object? value) => value is List ? value : const [];
  static Set<String> _strings(Object? value) =>
      value is List ? value.whereType<String>().toSet() : <String>{};
  static String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
  static String _liveLabel(String? phase) => switch (phase) {
    'arrival' => 'Arrivée et opération en cours',
    'live' => 'Opération en cours maintenant',
    _ => 'Situation opérationnelle à confirmer',
  };
}
