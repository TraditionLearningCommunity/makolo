import 'dart:async';

import 'package:flutter/material.dart';

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
import 'live_repository.dart';

class LiveScreen extends StatefulWidget {
  const LiveScreen({
    super.key,
    required this.occurrenceId,
    required this.repository,
    this.onBackToDayOf,
  });

  final String occurrenceId;
  final LiveRepository repository;
  final VoidCallback? onBackToDayOf;

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> with WidgetsBindingObserver {
  bool refreshing = false;

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
      await widget.repository.refresh(widget.occurrenceId);
    } on Object {
      // The sync source preserves the last honest snapshot and its error state.
    } finally {
      if (mounted) setState(() => refreshing = false);
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
        final available = base != null;
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
                  : 'La situation en direct n’est pas disponible dans ce contexte.',
              onRetry: _refresh,
              content: _LiveContent(
                payload: projection?.payload,
                freshness: base?.freshness,
                onBackToDayOf: widget.onBackToDayOf,
              ),
            ),
          ),
        );
      },
    ),
  );
}

class _LiveContent extends StatelessWidget {
  const _LiveContent({
    required this.payload,
    required this.freshness,
    this.onBackToDayOf,
  });

  final Map<String, dynamic>? payload;
  final FreshnessState? freshness;
  final VoidCallback? onBackToDayOf;

  @override
  Widget build(BuildContext context) {
    final data = payload ?? const <String, dynamic>{};
    final occurrence = _map(data['occurrence']);
    final timing = _map(data['timing']);
    final spatial = _map(data['spatial']);
    final place = _map(spatial['place']);
    final next = _map(data['next_action']);
    final queue = data['queue'] is List ? (data['queue'] as List).length : 0;
    final phase = _text(data['phase']) ?? 'unknown';
    return ListView(
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        if (onBackToDayOf != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: onBackToDayOf,
              icon: const Icon(Icons.arrow_back_rounded),
              label: const Text('Retour au Jour J'),
            ),
          ),
        Text(
          _text(occurrence['label']) ?? 'Occurrence en cours',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: MakoloSpacing.sm),
        Text(
          _phaseLabel(phase),
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (freshness == FreshnessState.usableButOld ||
            freshness == FreshnessState.refreshRecommended) ...[
          const SizedBox(height: MakoloSpacing.sm),
          const MakoloAttentionBlock(
            title: 'Dernière information connue',
            body: 'La connexion doit être vérifiée pour confirmer la situation actuelle.',
            icon: Icons.schedule_rounded,
          ),
        ],
        const SizedBox(height: MakoloSpacing.xl),
        MakoloSection(
          title: 'Ce qui compte maintenant',
          child: MakoloCard(
            child: Text(
              _text(next['label']) ?? 'Aucune action supplémentaire confirmée.',
            ),
          ),
        ),
        const SizedBox(height: MakoloSpacing.lg),
        MakoloSection(
          title: 'Repères',
          child: MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_text(place['name']) != null) Text(_text(place['name'])!),
                if (_text(_map(spatial['zone'])['name']) != null)
                  Text(_text(_map(spatial['zone'])['name'])!),
                if (_text(timing['temporal_state']) != null)
                  Text('Temps : ${_text(timing['temporal_state'])}'),
                if (queue > 0)
                  Text('Votre file : $queue élément${queue > 1 ? 's' : ''}'),
                if (place.isEmpty && queue == 0)
                  const Text('Aucun repère observé supplémentaire.'),
              ],
            ),
          ),
        ),
      ],
    );
  }

  static Map<String, dynamic> _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : const {};
  static String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
  static String _phaseLabel(String phase) => switch (phase) {
    'arrival' => 'Approche et arrivée',
    'live' => 'En cours maintenant',
    _ => 'Situation à confirmer',
  };
}
