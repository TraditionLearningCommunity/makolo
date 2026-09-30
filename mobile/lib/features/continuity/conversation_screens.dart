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
import 'conversation_repository.dart';

class ConversationListScreen extends StatefulWidget {
  const ConversationListScreen({
    super.key,
    required this.repository,
    required this.onOpen,
  });

  final ConversationRepository repository;
  final void Function(String id) onOpen;

  @override
  State<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends State<ConversationListScreen> {
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
    final local = await widget.repository.readList();
    final source = await widget.repository.readListSource();
    if (!mounted) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = ConversationRepository.listFreshness.evaluate(
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
      await widget.repository.refreshList();
    } on Object {
      // Preserve the local collection.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchList(),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchListSource(),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final items = _ConversationSummary.fromProjection(projection);
            final freshness = projection == null
                ? null
                : ConversationRepository.listFreshness.evaluate(
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
                  ? items.isEmpty
                        ? MakoloAvailabilityCue.empty
                        : MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: const Text('Conversations'),
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
                empty: const MakoloEmptyState(
                  title: 'Aucune conversation',
                  body: 'Rien ne demande votre attention ici pour le moment.',
                ),
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement des conversations…',
                ),
                onRetry: _refresh,
                content: ListView.separated(
                  key: const Key('conversation-list-content'),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  itemCount: items.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: MakoloSpacing.sm),
                  itemBuilder: (context, index) => MakoloCard(
                    onTap: () => widget.onOpen(items[index].id),
                    child: MakoloStatusMetadataAction(
                      title: items[index].title,
                      subtitle: items[index].contextLabel,
                      status: MakoloStatus(label: items[index].lifecycle),
                      metadata: [
                        if (items[index].attentionCount > 0)
                          MakoloMetadataItem(
                            items[index].attentionCount.toString() +
                                ' élément(s) à voir',
                            icon: Icons.notifications_active_outlined,
                          ),
                        if (items[index].allClear)
                          const MakoloMetadataItem(
                            'Tout est en ordre',
                            icon: Icons.check_circle_outline_rounded,
                          ),
                      ],
                      action: const Icon(Icons.chevron_right_rounded),
                    ),
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

class ConversationDetailScreen extends StatefulWidget {
  const ConversationDetailScreen({
    super.key,
    required this.id,
    required this.repository,
  });

  final String id;
  final ConversationRepository repository;

  @override
  State<ConversationDetailScreen> createState() =>
      _ConversationDetailScreenState();
}

class _ConversationDetailScreenState extends State<ConversationDetailScreen> {
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
    final local = await widget.repository.readDetail(widget.id);
    final source = await widget.repository.readDetailSource(widget.id);
    if (!mounted) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = ConversationRepository.detailFreshness.evaluate(
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
      await widget.repository.refreshDetail(widget.id);
    } on Object {
      // Preserve the local detail.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchDetail(widget.id),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchDetailSource(widget.id),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final detail = _ConversationDetail.fromProjection(projection);
            final freshness = projection == null
                ? null
                : ConversationRepository.detailFreshness.evaluate(
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
              failure: !available && source.invalidated && !_refreshing
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: const Text('Conversation'),
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
                  label: 'Chargement de la conversation…',
                ),
                blockingErrorMessage: 'Cette conversation n’est pas disponible dans votre contexte actuel.',
                onRetry: _refresh,
                content: ListView(
                  key: const Key('conversation-detail-content'),
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: detail.contextLabel,
                      title: detail.title,
                      subtitle: detail.purpose,
                      status: detail.lifecycle == null
                          ? null
                          : MakoloStatus(label: detail.lifecycle!),
                    ),
                    MakoloSection(
                      title: 'Points',
                      description: 'Les possibilités de réponse et l’attention requise viennent du serveur.',
                      child: detail.points.isEmpty
                          ? const MakoloCard(
                              child: Text('Aucun point à afficher.'),
                            )
                          : Column(
                              children: [
                                for (
                                  var index = 0;
                                  index < detail.points.length;
                                  index++
                                ) ...[
                                  _PointCard(point: detail.points[index]),
                                  if (index < detail.points.length - 1)
                                    const SizedBox(height: MakoloSpacing.sm),
                                ],
                              ],
                            ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _PointCard extends StatelessWidget {
  const _PointCard({required this.point});

  final _ConversationPoint point;

  @override
  Widget build(BuildContext context) {
    final metadata = <MakoloMetadataItem>[
      if (point.attentionReason != null)
        MakoloMetadataItem(
          point.attentionReason!,
          icon: Icons.priority_high_rounded,
        ),
      if (point.section != null) MakoloMetadataItem(point.section!),
      if (point.requiresAcknowledgement)
        const MakoloMetadataItem(
          'Confirmation de lecture requise',
          icon: Icons.visibility_outlined,
        ),
      if (point.canRespond)
        const MakoloMetadataItem(
          'Réponse autorisée par le serveur',
          icon: Icons.reply_rounded,
        ),
    ];
    return MakoloCard(
      child: MakoloStatusMetadataAction(
        title: point.title,
        subtitle: point.body,
        status: MakoloStatus(label: point.lifecycle),
        metadata: metadata,
      ),
    );
  }
}

class _ConversationSummary {
  const _ConversationSummary({
    required this.id,
    required this.title,
    required this.lifecycle,
    required this.attentionCount,
    required this.allClear,
    this.contextLabel,
  });

  final String id;
  final String title;
  final String lifecycle;
  final int attentionCount;
  final bool allClear;
  final String? contextLabel;

  static List<_ConversationSummary> fromProjection(
    StoredProjection? projection,
  ) {
    final raw = projection?.payload['results'];
    if (raw is! List) return const [];
    return raw
        .map((item) {
          final row = _map(item);
          final context = _map(row['context']);
          return _ConversationSummary(
            id: _string(row['id']) ?? '',
            title: _string(row['title']) ?? 'Conversation',
            lifecycle: _string(row['lifecycle']) ?? '',
            attentionCount: row['attention_count'] is num
                ? (row['attention_count'] as num).toInt()
                : 0,
            allClear: row['all_clear'] == true,
            contextLabel: _string(context['label']),
          );
        })
        .where((item) => item.id.isNotEmpty)
        .toList(growable: false);
  }
}

class _ConversationDetail {
  const _ConversationDetail({
    required this.title,
    required this.points,
    this.purpose,
    this.lifecycle,
    this.contextLabel,
  });

  final String title;
  final String? purpose;
  final String? lifecycle;
  final String? contextLabel;
  final List<_ConversationPoint> points;

  factory _ConversationDetail.fromProjection(StoredProjection? projection) {
    if (projection == null) {
      return const _ConversationDetail(title: 'Conversation', points: []);
    }
    final payload = projection.payload;
    final context = _map(payload['context']);
    return _ConversationDetail(
      title: _string(payload['title']) ?? 'Conversation',
      purpose: _string(payload['purpose']),
      lifecycle: _string(payload['lifecycle']),
      contextLabel: _string(context['label']),
      points: _maps(payload['points'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
    );
  }
}

class _ConversationPoint {
  const _ConversationPoint({
    required this.title,
    required this.lifecycle,
    required this.requiresAcknowledgement,
    required this.canRespond,
    this.body,
    this.attentionReason,
    this.section,
  });

  final String title;
  final String? body;
  final String lifecycle;
  final bool requiresAcknowledgement;
  final bool canRespond;
  final String? attentionReason;
  final String? section;

  factory _ConversationPoint.fromMap(Map<String, dynamic> row) {
    return _ConversationPoint(
      title: _string(row['title']) ?? 'Point',
      body: _string(row['body']),
      lifecycle: _string(row['lifecycle']) ?? '',
      requiresAcknowledgement: row['requires_acknowledgement'] == true,
      canRespond: row['can_respond'] == true,
      attentionReason: _string(row['attention_reason']),
      section: _string(row['section']),
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
