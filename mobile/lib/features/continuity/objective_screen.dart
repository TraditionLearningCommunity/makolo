import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'objective_repository.dart';

class ObjectiveDetailScreen extends StatefulWidget {
  const ObjectiveDetailScreen({
    super.key,
    required this.kind,
    required this.id,
    required this.repository,
    required this.onOpenDossier,
    required this.onOpenJourney,
  });

  final ObjectiveDepth kind;
  final String id;
  final ObjectiveRepository repository;
  final void Function(String id) onOpenDossier;
  final void Function(String id) onOpenJourney;

  @override
  State<ObjectiveDetailScreen> createState() => _ObjectiveDetailScreenState();
}

class _ObjectiveDetailScreenState extends State<ObjectiveDetailScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final local = await widget.repository.read(widget.kind, widget.id);
    final source = await widget.repository.readSource(widget.kind, widget.id);
    if (!mounted) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = ObjectiveRepository.freshnessPolicy.evaluate(
      local,
      now: DateTime.now(),
      invalidated: source.invalidated,
    );
    if (freshness != FreshnessState.fresh) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refresh(widget.kind, widget.id);
    } on Object {
      // The shared SyncSource keeps usable local content on transient failure.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watch(widget.kind, widget.id),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchSource(widget.kind, widget.id),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final freshness = projection == null
                ? null
                : ObjectiveRepository.freshnessPolicy.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = projection != null;
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: freshness,
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
              failure:
                  !available &&
                      (source.invalidated ||
                          source.reachability ==
                              ReachabilityState.unreachable) &&
                      !_refreshing
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: Text(
                  widget.kind == ObjectiveDepth.dossier ? 'Dossier' : 'Projet',
                ),
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
                    label: 'Chargement…',
                  ),
                  blockingErrorMessage: 'Ce contenu n’est pas disponible dans votre contexte actuel.',
                  onRetry: _refresh,
                  content: widget.kind == ObjectiveDepth.dossier
                      ? _DossierContent(
                          payload: projection?.payload ?? const {},
                          onOpenJourney: widget.onOpenJourney,
                        )
                      : _ProjectContent(
                          payload: projection?.payload ?? const {},
                          onOpenDossier: widget.onOpenDossier,
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

class _DossierContent extends StatelessWidget {
  const _DossierContent({required this.payload, required this.onOpenJourney});

  final Map<String, dynamic> payload;
  final void Function(String id) onOpenJourney;

  @override
  Widget build(BuildContext context) {
    final objective = _map(payload['objective']);
    final state = _map(payload['state']);
    final readiness = _map(payload['readiness']);
    final items = _maps(payload['visible_items']);
    final responsibilities = _maps(payload['personal_responsibilities']);
    final interventions = _maps(payload['actor_interventions']);
    final dependencies = _maps(payload['visible_dependencies']);

    return ListView(
      key: const Key('dossier-detail-content'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        MakoloDetailHeader(
          eyebrow: 'Dossier',
          title: _string(objective['title']) ?? 'Dossier',
          subtitle: _string(objective['description']),
          status: _humanState(state['label'] ?? state['code']) == null
              ? null
              : MakoloStatus(
                  label: _humanState(state['label'] ?? state['code'])!,
                ),
          metadata: [
            if (_humanDate(payload['deadline']) != null)
              MakoloMetadataItem(
                'Échéance ${_humanDate(payload['deadline'])!}',
              ),
          ],
        ),
        MakoloSection(
          title: 'État collectif',
          description: readiness['partial'] == true
              ? 'Vue partielle selon ce que vous êtes autorisé à voir.'
              : null,
          child: MakoloCard(
            child: MakoloStatusMetadataAction(
              title:
                  _string(readiness['label']) ??
                  _humanState(readiness['state']) ??
                  'Situation',
              subtitle: _string(readiness['hidden_signal']),
            ),
          ),
        ),
        if (interventions.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.xl),
          MakoloSection(
            title: 'Votre prochaine intervention',
            child: Column(
              children: [
                for (final row in interventions)
                  MakoloCard(
                    onTap: _string(row['journey_id']) == null
                        ? null
                        : () => onOpenJourney(_string(row['journey_id'])!),
                    child: MakoloStatusMetadataAction(
                      title: _string(row['label']) ?? 'Action',
                      status: _humanState(row['state']) == null
                          ? null
                          : MakoloStatus(label: _humanState(row['state'])!),
                      action: _string(row['journey_id']) == null
                          ? null
                          : const Icon(Icons.chevron_right_rounded),
                    ),
                  ),
              ],
            ),
          ),
        ],
        if (items.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.xl),
          MakoloSection(
            title: 'Démarches visibles',
            child: Column(
              children: [
                for (var index = 0; index < items.length; index++) ...[
                  MakoloCard(
                    onTap: _string(items[index]['journey_id']) == null
                        ? null
                        : () => onOpenJourney(
                            _string(items[index]['journey_id'])!,
                          ),
                    child: MakoloStatusMetadataAction(
                      title: _string(items[index]['label']) ?? 'Démarche',
                      subtitle: items[index]['hidden_dependency'] == true
                          ? 'Une dépendance non divulguée influence cet état.'
                          : null,
                      status: _humanState(items[index]['state']) == null
                          ? null
                          : MakoloStatus(
                              label: _humanState(items[index]['state'])!,
                            ),
                      action: const Icon(Icons.chevron_right_rounded),
                    ),
                  ),
                  if (index < items.length - 1)
                    const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
            ),
          ),
        ],
        if (dependencies.isNotEmpty || responsibilities.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.xl),
          MakoloSection(
            title: 'Continuité',
            child: Column(
              children: [
                if (responsibilities.isNotEmpty)
                  MakoloCard(
                    child: Text(
                      responsibilities.length == 1
                          ? '1 responsabilité personnelle active.'
                          : '${responsibilities.length} responsabilités personnelles actives.',
                    ),
                  ),
                if (responsibilities.isNotEmpty && dependencies.isNotEmpty)
                  const SizedBox(height: MakoloSpacing.sm),
                if (dependencies.isNotEmpty)
                  MakoloCard(
                    child: Text(
                      dependencies.length == 1
                          ? '1 dépendance visible entre démarches.'
                          : '${dependencies.length} dépendances visibles entre démarches.',
                    ),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _ProjectContent extends StatelessWidget {
  const _ProjectContent({required this.payload, required this.onOpenDossier});

  final Map<String, dynamic> payload;
  final void Function(String id) onOpenDossier;

  @override
  Widget build(BuildContext context) {
    final horizon = _map(payload['horizon']);
    final state = _map(payload['state']);
    final dossiers = _maps(payload['visible_dossiers']);
    final metadata = <MakoloMetadataItem>[
      if (_string(horizon['starts_on']) != null)
        MakoloMetadataItem('Début ${_string(horizon['starts_on'])!}'),
      if (_string(horizon['ends_on']) != null)
        MakoloMetadataItem('Fin ${_string(horizon['ends_on'])!}'),
    ];

    return ListView(
      key: const Key('project-detail-content'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        MakoloDetailHeader(
          eyebrow: 'Projet',
          title: _string(horizon['title']) ?? 'Projet',
          subtitle: _string(horizon['description']),
          status: _humanState(state['label'] ?? state['code']) == null
              ? null
              : MakoloStatus(
                  label: _humanState(state['label'] ?? state['code'])!,
                ),
          metadata: metadata,
        ),
        MakoloSection(
          title: 'Dossiers',
          description:
              'Seuls les dossiers que vous êtes autorisé à voir sont affichés.',
          child: dossiers.isEmpty
              ? const MakoloCard(
                  child: Text('Aucun dossier visible pour le moment.'),
                )
              : Column(
                  children: [
                    for (var index = 0; index < dossiers.length; index++) ...[
                      MakoloCard(
                        onTap: _string(dossiers[index]['id']) == null
                            ? null
                            : () => onOpenDossier(
                                _string(dossiers[index]['id'])!,
                              ),
                        child: MakoloStatusMetadataAction(
                          title: _string(dossiers[index]['title']) ?? 'Dossier',
                          status: _humanState(dossiers[index]['state']) == null
                              ? null
                              : MakoloStatus(
                                  label: _humanState(dossiers[index]['state'])!,
                                ),
                          metadata: [
                            if (_humanDate(dossiers[index]['deadline']) != null)
                              MakoloMetadataItem(
                                'Échéance ${_humanDate(dossiers[index]['deadline'])!}',
                              ),
                          ],
                          action: const Icon(Icons.chevron_right_rounded),
                        ),
                      ),
                      if (index < dossiers.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const [];
  return value.map(_map).where((row) => row.isNotEmpty).toList(growable: false);
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

String? _humanState(Object? value) =>
    MakoloHumanization.presentationLabel(_string(value));

String? _humanDate(Object? value) {
  final raw = _string(value);
  if (raw == null) return null;
  final instant = MakoloHumanization.tryParseInstant(raw);
  if (instant == null) return raw;
  return MakoloHumanization.formatDay(instant, now: DateTime.now());
}
