import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'preparation_repository.dart';

class RequirementDetailScreen extends StatefulWidget {
  const RequirementDetailScreen({
    super.key,
    required this.journeyId,
    required this.assessmentId,
    required this.repository,
    this.detailPath,
  });

  final String journeyId;
  final String assessmentId;
  final RequirementRepository repository;
  final String? detailPath;

  @override
  State<RequirementDetailScreen> createState() =>
      _RequirementDetailScreenState();
}

class _RequirementDetailScreenState extends State<RequirementDetailScreen> {
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
    final local = await widget.repository.readDetail(widget.assessmentId);
    final source = await widget.repository.readSource(widget.assessmentId);
    if (!mounted) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = RequirementRepository.freshnessPolicy.evaluate(
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
      await widget.repository.refresh(
        journeyId: widget.journeyId,
        assessmentId: widget.assessmentId,
        detailPath: widget.detailPath,
      );
    } on Object {
      // SyncSource records the failure and preserves usable local content.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchDetail(widget.assessmentId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchSource(widget.assessmentId),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final freshness = projection == null
                ? null
                : RequirementRepository.freshnessPolicy.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final presentation = _RequirementPresentation.from(projection);
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
              failure: !available && source.invalidated && !_refreshing
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );

            return Scaffold(
              appBar: AppBar(
                title: const Text('Élément nécessaire'),
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
                  label: 'Chargement de l’élément nécessaire…',
                ),
                blockingErrorMessage: 'Cet élément n’est pas disponible dans votre contexte actuel.',
                preservedMessage: 'Aucune copie locale utilisable n’est disponible sur cet appareil.',
                onRetry: _refresh,
                content: _RequirementContent(presentation: presentation),
              ),
            );
          },
        );
      },
    );
  }
}

class _RequirementContent extends StatelessWidget {
  const _RequirementContent({required this.presentation});

  final _RequirementPresentation presentation;

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const Key('requirement-detail-content'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        MakoloDetailHeader(
          eyebrow: presentation.required ? 'Obligatoire' : 'Condition',
          title: presentation.label,
          subtitle: presentation.description,
          status: presentation.state == null
              ? null
              : MakoloStatus(label: presentation.state!),
        ),
        if (presentation.consequence != null) ...[
          MakoloSection(
            title: 'Conséquence',
            child: MakoloCard(child: Text(presentation.consequence!)),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        MakoloSection(
          title: 'Comment avancer',
          description:
              'Ces possibilités sont fournies par le domaine propriétaire.',
          child: presentation.ways.isEmpty
              ? const MakoloCard(
                  child: Text(
                    'Aucune manière de satisfaire supplémentaire n’est exposée pour le moment.',
                  ),
                )
              : Column(
                  children: [
                    for (
                      var index = 0;
                      index < presentation.ways.length;
                      index++
                    ) ...[
                      MakoloCard(
                        child: MakoloStatusMetadataAction(
                          title: presentation.ways[index].label,
                          status: presentation.ways[index].state == null
                              ? null
                              : MakoloStatus(
                                  label: presentation.ways[index].state!,
                                ),
                        ),
                      ),
                      if (index < presentation.ways.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

class _RequirementWay {
  const _RequirementWay({required this.label, this.state});

  final String label;
  final String? state;
}

class _RequirementPresentation {
  const _RequirementPresentation({
    required this.label,
    required this.required,
    required this.ways,
    this.description,
    this.state,
    this.consequence,
  });

  final String label;
  final bool required;
  final String? description;
  final String? state;
  final String? consequence;
  final List<_RequirementWay> ways;

  factory _RequirementPresentation.from(StoredProjection? projection) {
    if (projection == null) {
      return const _RequirementPresentation(
        label: 'Élément nécessaire',
        required: false,
        ways: [],
      );
    }
    final payload = projection.payload;
    final requirement = _map(payload['requirement']);
    final assessment = _map(payload['assessment']);
    final ways = _maps(payload['ways_to_satisfy'])
        .map(
          (row) => _RequirementWay(
            label: _wayLabel(row),
            state: _string(row['state']),
          ),
        )
        .toList(growable: false);
    return _RequirementPresentation(
      label: _string(requirement['label']) ?? 'Élément nécessaire',
      required: requirement['required'] == true,
      description: _string(requirement['description']),
      state: _string(assessment['state']),
      consequence: _string(assessment['consequence']),
      ways: ways,
    );
  }

  static String _wayLabel(Map<String, dynamic> row) {
    final explicit = _string(row['label']);
    if (explicit != null) return explicit;
    return switch (_string(row['kind'])) {
      'payment' => 'Paiement',
      'journey_step' => 'Étape de la démarche',
      _ => 'Possibilité',
    };
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
