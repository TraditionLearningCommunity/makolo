import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
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
import 'conversation_repository.dart';

class ConversationListScreen extends StatefulWidget {
  const ConversationListScreen({
    super.key,
    required this.repository,
    required this.onOpen,
    this.onOpenPoint,
  });

  final ConversationRepository repository;
  final void Function(String id) onOpen;
  final void Function(String id, String pointId)? onOpenPoint;

  @override
  State<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends State<ConversationListScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;
  bool _attemptedRefresh = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  @override
  void didUpdateWidget(covariant ConversationListScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _requestedInitialRefresh = false;
      _attemptedRefresh = false;
      _refreshing = false;
      unawaited(_acquireOrRefresh());
    }
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final repository = widget.repository;
    try {
      final local = await repository.readList();
      final source = await repository.readListSource();
      if (!mounted || repository != widget.repository) return;
      unawaited(_refreshInvitationsIfNeeded());
      if (local == null) {
        await _refreshList();
        return;
      }
      final freshness = ConversationRepository.listFreshness.evaluate(
        local,
        now: DateTime.now(),
        invalidated: source.invalidated,
      );
      if (freshness != FreshnessState.fresh) await _refreshList();
    } on Object {
      // Even a failed local read must end the initial loading state.
      if (mounted && repository == widget.repository) {
        setState(() => _attemptedRefresh = true);
      }
    }
  }

  Future<void> _refreshInvitationsIfNeeded({bool force = false}) async {
    final repository = widget.repository;
    try {
      final invitations = await repository.readInvitations();
      final source = await repository.readInvitationsSource();
      if (force ||
          invitations == null ||
          ConversationRepository.invitationsFreshness.evaluate(
                invitations,
                now: DateTime.now(),
                invalidated: source.invalidated,
              ) != FreshnessState.fresh) {
        await repository.refreshInvitations();
      }
    } on Object {
      // Invitation errors are independent from the conversation list.
    }
  }

  Future<void> _refresh() async {
    unawaited(_refreshInvitationsIfNeeded(force: true));
    await _refreshList();
  }

  Future<void> _refreshList() async {
    if (_refreshing) return;
    final repository = widget.repository;
    setState(() => _refreshing = true);
    try {
      await repository.refreshList();
    } on Object {
      // Retain the local owner snapshot during transport failures.
    } finally {
      if (mounted && repository == widget.repository) {
        setState(() {
          _refreshing = false;
          _attemptedRefresh = true;
        });
      }
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
              // An empty list can still contain pending invitations.
              availability: available
                  ? MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: source.lastErrorCode == 'permission_denied'
                  ? MakoloFailureCue.permissionDenied
                  : source.lastErrorCode == 'not_found'
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null || (!available && _attemptedRefresh)
                  ? available ? MakoloFailureCue.recoverable : MakoloFailureCue.blocking
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
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement des conversations…',
                ),
                blockingErrorMessage: 'Impossible de charger vos conversations.',
                recoverableErrorMessage: 'Mise à jour impossible pour le moment.',
                preservedMessage: available
                    ? 'Les conversations déjà disponibles restent consultables.'
                    : null,
                onRetry: _refresh,
                content: _ConversationListBody(
                  repository: widget.repository,
                  items: items,
                  onOpen: widget.onOpen,
                  onOpenPoint: widget.onOpenPoint,
                  onRetryInvitations: () => _refreshInvitationsIfNeeded(force: true),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _ConversationListBody extends StatefulWidget {
  const _ConversationListBody({
    required this.repository,
    required this.items,
    required this.onOpen,
    required this.onRetryInvitations,
    this.onOpenPoint,
  });

  final ConversationRepository repository;
  final List<_ConversationSummary> items;
  final void Function(String id) onOpen;
  final void Function(String id, String pointId)? onOpenPoint;
  final Future<void> Function() onRetryInvitations;

  @override
  State<_ConversationListBody> createState() => _ConversationListBodyState();
}

class _ConversationListBodyState extends State<_ConversationListBody> {
  String _query = '';
  Timer? _debounce;
  int _searchGeneration = 0;
  bool _searching = false;
  bool _searchFailed = false;
  List<_ConversationSummary> _remote = const [];

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant _ConversationListBody oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _debounce?.cancel();
      _searchGeneration++;
      _remote = const [];
      _searching = false;
      _searchFailed = false;
      if (_query.trim().isNotEmpty) _scheduleSearch(_query);
    }
  }

  void _scheduleSearch(String query) {
    _debounce?.cancel();
    final generation = ++_searchGeneration;
    setState(() {
      _query = query;
      _remote = const [];
      _searchFailed = false;
      _searching = query.trim().isNotEmpty;
    });
    if (!_searching) return;
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      try {
        final results = await widget.repository.searchConversations(query);
        if (!mounted || generation != _searchGeneration) return;
        setState(() {
          _remote = results
              .map(_ConversationSummary.fromMap)
              .where((item) => item.id.isNotEmpty)
              .toList(growable: false);
          _searching = false;
        });
      } on Object {
        if (!mounted || generation != _searchGeneration) return;
        setState(() {
          _searching = false;
          _searchFailed = true;
        });
      }
    });
  }

  List<_ConversationSummary> _matchingRows() {
    final normalized = _query.trim().toLowerCase();
    if (normalized.isEmpty) return widget.items;
    final known = <String, _ConversationSummary>{};
    for (final item in widget.items) {
      if (item.title.toLowerCase().contains(normalized) ||
          (item.purpose ?? '').toLowerCase().contains(normalized) ||
          (item.contextLabel ?? '').toLowerCase().contains(normalized) ||
          (item.latestResult ?? '').toLowerCase().contains(normalized)) {
        known[item.id] = item;
      }
    }
    // Owner results win for their focused Point, without duplicating a row.
    for (final result in _remote) {
      known[result.id] = result;
    }
    return known.values.toList(growable: false);
  }

  void _open(_ConversationSummary item) {
    final point = item.matchedPointId;
    if (point != null && widget.onOpenPoint != null) {
      widget.onOpenPoint!(item.id, point);
    } else {
      widget.onOpen(item.id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _matchingRows();
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchInvitations(),
      builder: (context, invitationsSnapshot) {
        final invitations = _ConversationInvitation.fromProjection(
          invitationsSnapshot.data,
        );
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchInvitationsSource(),
          initialData: OwnerSourceState.unknown,
          builder: (context, invitationSourceSnapshot) {
            final invitationFailure =
                invitationSourceSnapshot.data?.lastErrorCode != null;
            return ListView(
              key: const Key('conversation-list-content'),
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.inner,
                vertical: MakoloSpacing.md,
              ),
              children: [
                TextField(
                  key: const Key('conversation-search-field'),
                  onChanged: _scheduleSearch,
                  decoration: InputDecoration(
                    hintText: 'Rechercher une conversation…',
                    prefixIcon: const Icon(Icons.search_rounded),
                    suffixIcon: _searching
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: Center(
                              child: SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              ),
                            ),
                          )
                        : null,
                  ),
                ),
                if (_searchFailed)
                  const Padding(
                    padding: EdgeInsets.only(top: MakoloSpacing.sm),
                    child: Text('Recherche en ligne indisponible.'),
                  ),
                if (invitationFailure && _query.isEmpty) ...[
                  const SizedBox(height: MakoloSpacing.md),
                  const Text('Impossible d’actualiser les invitations.'),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      onPressed: () => unawaited(widget.onRetryInvitations()),
                      child: const Text('Réessayer'),
                    ),
                  ),
                ],
                if (invitations.isNotEmpty && _query.isEmpty) ...[
                  const SizedBox(height: MakoloSpacing.lg),
                  Text('Invitations',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: MakoloSpacing.sm),
                  for (final invitation in invitations) ...[
                    _ConversationInvitationCard(
                      invitation: invitation,
                      repository: widget.repository,
                      onOpen: widget.onOpen,
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                  ],
                ],
                const SizedBox(height: MakoloSpacing.lg),
                if (filtered.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
                    child: Text(
                      _query.trim().isEmpty
                          ? 'Aucune conversation à afficher.'
                          : _searching
                          ? 'Recherche…'
                          : 'Aucun résultat.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  )
                else
                  for (final item in filtered) ...[
                    Material(
                      type: MaterialType.transparency,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(MakoloRadii.medium),
                        onTap: () => _open(item),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: MakoloSpacing.md,
                            horizontal: MakoloSpacing.sm,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    if (item.contextLabel != null)
                                      Text(
                                        item.contextLabel!,
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                    const SizedBox(height: 4),
                                    Text(
                                      item.title,
                                      style: Theme.of(context).textTheme.titleMedium,
                                    ),
                                    if (item.latestResult != null)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 6),
                                        child: Text('✓ ${item.latestResult!}'),
                                      )
                                    else if (item.purpose != null)
                                      Padding(
                                        padding: const EdgeInsets.only(top: 4),
                                        child: Text(
                                          item.purpose!,
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: MakoloSpacing.sm),
                              if (item.attentionCount > 0)
                                Text(
                                  '${item.attentionCount} à traiter',
                                  style: Theme.of(context).textTheme.labelMedium,
                                )
                              else
                                const Icon(Icons.chevron_right_rounded, size: 20),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const Divider(height: 1),
                  ],
              ],
            );
          },
        );
      },
    );
  }
}

class _ConversationInvitationCard extends StatefulWidget {
  const _ConversationInvitationCard({
    required this.invitation,
    required this.repository,
    required this.onOpen,
  });

  final _ConversationInvitation invitation;
  final ConversationRepository repository;
  final void Function(String id) onOpen;

  @override
  State<_ConversationInvitationCard> createState() =>
      _ConversationInvitationCardState();
}

class _ConversationInvitationCardState
    extends State<_ConversationInvitationCard> {
  bool _busy = false;
  String? _error;

  Future<void> _respond(bool accept) async {
    if (_busy || widget.invitation.expired) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final conversationId = await widget.repository.respondToInvitation(
        invitationId: widget.invitation.id,
        accept: accept,
      );
      if (!mounted) return;
      if (accept && conversationId != null) widget.onOpen(conversationId);
    } on Object {
      if (!mounted) return;
      setState(
        () => _error =
            'Cette invitation a changé. Actualisez pour voir son état actuel.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Invitation à rejoindre une coordination',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          if (widget.invitation.expired)
            const Padding(
              padding: EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text('Cette invitation a expiré.'),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(_error!),
            ),
          const SizedBox(height: MakoloSpacing.sm),
          Wrap(
            spacing: MakoloSpacing.sm,
            children: [
              OutlinedButton(
                onPressed: _busy || widget.invitation.expired
                    ? null
                    : () => _respond(false),
                child: const Text('Refuser'),
              ),
              FilledButton(
                onPressed: _busy || widget.invitation.expired
                    ? null
                    : () => _respond(true),
                child: Text(_busy ? 'En cours…' : 'Accepter'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ConversationDetailScreen extends StatefulWidget {
  const ConversationDetailScreen({
    super.key,
    required this.id,
    required this.repository,
    this.representedSpaceId,
    this.focusPointId,
  });

  final String id;
  final ConversationRepository repository;
  final String? representedSpaceId;
  final String? focusPointId;

  @override
  State<ConversationDetailScreen> createState() =>
      _ConversationDetailScreenState();
}

class _ConversationDetailScreenState extends State<ConversationDetailScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  final GlobalKey _pointFocusKey = GlobalKey();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;
  bool _attemptedRefresh = false;
  String? _handledFocus;

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  @override
  void didUpdateWidget(covariant ConversationDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.id != widget.id ||
        oldWidget.repository != widget.repository ||
        oldWidget.focusPointId != widget.focusPointId) {
      _handledFocus = null;
      _requestedInitialRefresh = false;
      _attemptedRefresh = false;
      _refreshing = false;
      unawaited(_acquireOrRefresh());
    }
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final repository = widget.repository;
    final id = widget.id;
    try {
      final local = await repository.readDetail(id);
      final source = await repository.readDetailSource(id);
      if (!mounted || repository != widget.repository || id != widget.id) return;
      if (local == null) {
        await _refresh();
        return;
      }
      final freshness = ConversationRepository.detailFreshness.evaluate(
        local,
        now: DateTime.now(),
        invalidated: source.invalidated,
      );
      if (freshness != FreshnessState.fresh || widget.focusPointId != null) {
        await _refresh();
      }
    } on Object {
      if (mounted && repository == widget.repository && id == widget.id) {
        setState(() => _attemptedRefresh = true);
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final repository = widget.repository;
    final id = widget.id;
    setState(() => _refreshing = true);
    try {
      await repository.refreshDetail(id, focusPointId: widget.focusPointId);
    } on Object {
      // Retain the authorized local detail during transport failures.
    } finally {
      if (mounted && repository == widget.repository && id == widget.id) {
        setState(() {
          _refreshing = false;
          _attemptedRefresh = true;
        });
      }
    }
  }

  Future<void> _updatePersonalState(
    String action,
    _ConversationPersonalState state,
  ) async {
    try {
      switch (action) {
        case 'pin':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            pinned: !state.pinned,
          );
          break;
        case 'mute':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            mute: !state.muted,
          );
          break;
        case 'archive':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            archived: !state.archived,
          );
          break;
        case 'hide':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            hidden: !state.hidden,
          );
          break;
        case 'revisit':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            revisit: !state.revisit,
          );
          break;
      }
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Modification non confirmée.',
          ),
        ),
      );
    }
  }

  Widget _pointWidget(_ConversationPoint point, {bool readOnly = false}) {
    final focused = point.id == widget.focusPointId;
    return Padding(
      key: focused ? _pointFocusKey : ValueKey('point-${point.id}'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: _PointCard(
        point: point,
        repository: widget.repository,
        conversationId: widget.id,
        representedSpaceId: widget.representedSpaceId,
        readOnly: readOnly,
      ),
    );
  }

  Widget _pointSection(
    BuildContext context,
    String title,
    List<_ConversationPoint> points, {
    bool readOnly = false,
  }) {
    if (points.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.inner, MakoloSpacing.lg,
        MakoloSpacing.inner, 0,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: MakoloSpacing.md),
          for (final point in points)
            _pointWidget(point, readOnly: readOnly),
        ],
      ),
    );
  }

  void _focusAfterLayout() {
    final id = widget.focusPointId;
    if (id == null || id == _handledFocus) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || id != widget.focusPointId) return;
      final focused = _pointFocusKey.currentContext;
      if (focused == null) return;
      _handledFocus = id;
      Scrollable.ensureVisible(
        focused,
        duration: const Duration(milliseconds: 250),
        alignment: 0.18,
      );
    });
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
              failure: source.lastErrorCode == 'permission_denied'
                  ? MakoloFailureCue.permissionDenied
                  : source.lastErrorCode == 'not_found' ||
                        (!available && source.invalidated)
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null || (!available && _attemptedRefresh)
                  ? available ? MakoloFailureCue.recoverable : MakoloFailureCue.blocking
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: Text(
                  available ? detail.title : 'Conversation',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                actions: [
                  PopupMenuButton<String>(
                    tooltip: 'État personnel',
                    onSelected: (action) =>
                        _updatePersonalState(action, detail.personalState),
                    itemBuilder: (context) => [
                      PopupMenuItem(
                        value: 'pin',
                        child: Text(
                          detail.personalState.pinned
                              ? 'Retirer l’épingle'
                              : 'Épingler pour moi',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'mute',
                        child: Text(
                          detail.personalState.muted
                              ? 'Réactiver les signaux'
                              : 'Mettre les signaux en sourdine',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'revisit',
                        child: Text(
                          detail.personalState.revisit
                              ? 'Retirer le rappel de revisite'
                              : 'Revoir plus tard',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'archive',
                        child: Text(
                          detail.personalState.archived
                              ? 'Retirer de mes archives'
                              : 'Archiver pour moi',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'hide',
                        child: Text(
                          detail.personalState.hidden
                              ? 'Afficher de nouveau'
                              : 'Masquer pour moi',
                        ),
                      ),
                    ],
                  ),
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
                blockingErrorMessage: 'Cette conversation est indisponible ou n’a pas pu être chargée.',
                recoverableErrorMessage: 'Mise à jour impossible pour le moment.',
                preservedMessage: available
                    ? 'La dernière version disponible reste consultable.'
                    : null,
                onRetry: _refresh,
                content: Builder(
                  builder: (context) {
                    final seen = <String>{};
                    List<_ConversationPoint> unique(Iterable<_ConversationPoint> points) {
                      return [
                        for (final point in points)
                          if (seen.add(point.id)) point,
                      ];
                    }

                    final focused = detail.focusedPoint;
                    final focusedOnly = focused != null &&
                            !detail.points.any((p) => p.id == focused.id) &&
                            !detail.elsewhere.any((p) => p.id == focused.id) &&
                            !detail.essential.any((p) => p.id == focused.id)
                        ? unique([focused])
                        : <_ConversationPoint>[];
                    final essential = unique(detail.essential);
                    final mine = unique(detail.points.where(
                      (point) => point.section == 'pour_moi' ||
                          point.attentionReason == 'resolve',
                    ));
                    final elsewhere = unique(detail.elsewhere);
                    final information = unique(detail.points.where(
                      (point) => point.section != 'pour_moi' &&
                          point.attentionReason != 'resolve',
                    ));
                    _focusAfterLayout();

                    return ListView(
                      key: const Key('conversation-detail-content'),
                      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(
                            MakoloSpacing.inner, MakoloSpacing.md,
                            MakoloSpacing.inner, 0,
                          ),
                          child: MakoloDetailHeader(
                            eyebrow: detail.contextLabel,
                            title: detail.title,
                            subtitle: detail.purpose,
                            status: detail.lifecycle == null
                                ? null
                                : MakoloStatus(label: detail.lifecycle!),
                          ),
                        ),
                        _pointSection(context, 'Point recherché', focusedOnly),
                        _pointSection(context, 'L’essentiel', essential, readOnly: true),
                        _pointSection(context, 'À vous', mine),
                        _pointSection(context, 'En cours ailleurs', elsewhere, readOnly: true),
                        _pointSection(context, 'À savoir et résultats', information, readOnly: true),
                        if (focusedOnly.isEmpty && essential.isEmpty &&
                            mine.isEmpty && elsewhere.isEmpty &&
                            information.isEmpty)
                          const Padding(
                            padding: EdgeInsets.all(MakoloSpacing.inner),
                            child: Text('Tout est en ordre. ✓'),
                          ),
                      ],
                    );
                  },
                ),
              );
          },
        );
      },
    );
  }
}

class _PointCard extends StatefulWidget {
  const _PointCard({
    required this.point,
    required this.repository,
    required this.conversationId,
    this.representedSpaceId,
    this.readOnly = false,
  });

  final _ConversationPoint point;
  final ConversationRepository repository;
  final String conversationId;
  final String? representedSpaceId;
  final bool readOnly;

  @override
  State<_PointCard> createState() => _PointCardState();
}

class _PointCardState extends State<_PointCard> {
  bool _busy = false;
  String? _feedback;
  String? _clientReference;
  Object? _lastValue;
  final Set<String> _choices = {};

  String _referenceFor(Object? value) {
    if (_lastValue.toString() != value.toString()) {
      _clientReference = null;
    }
    _lastValue = value;
    _clientReference ??=
        'mobile-${widget.point.id}-${DateTime.now().microsecondsSinceEpoch}';
    return _clientReference!;
  }

  Future<void> _acknowledge() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.repository.acknowledgePoint(
        conversationId: widget.conversationId,
        pointId: widget.point.id,
      );
    } on Object {
      try {
        await widget.repository.refreshDetail(widget.conversationId);
      } on Object {
        // Keep the last authorized snapshot.
      }
      if (mounted) {
        setState(() => _feedback = 'Lecture non confirmée. Réessayez.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submitResponse(Object? value) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.repository.respondToPoint(
        conversationId: widget.conversationId,
        pointId: widget.point.id,
        value: value,
        clientReference: _referenceFor(value),
        representedSpaceId: widget.representedSpaceId,
      );
      _clientReference = null;
      if (mounted) setState(() => _choices.clear());
    } on Object {
      try {
        await widget.repository.refreshDetail(widget.conversationId);
      } on Object {
        // The response remains unconfirmed until the owner can be reached.
      }
      if (mounted) {
        setState(() => _feedback = 'Envoi non confirmé. Vérifiez avant de réessayer.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _respond() async {
    if (_busy) return;
    final value = await _collectResponseValue(context, widget.point);
    if (!mounted || identical(value, _cancelledResponse)) return;
    await _submitResponse(value);
  }

  @override
  Widget build(BuildContext context) {
    final point = widget.point;
    final interactive = !widget.readOnly &&
        (point.canRespond || point.attentionReason == 'acknowledge');
    final kindLabel = switch (point.kind) {
      'information' => 'Information',
      'poll' => 'Sondage',
      'confirmation' => 'Confirmation',
      'question' => 'Question',
      'request' => 'Demande',
      'form_request' => 'Formulaire',
      'exchange' => 'Échange',
      _ => 'Point',
    };
    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(kindLabel, style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 6),
        Text(point.title, style: Theme.of(context).textTheme.titleMedium),
        if (point.body != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text(point.body!),
        ],
        if (point.deadlineAt != null && point.canRespond) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'Avant le ${MaterialLocalizations.of(context).formatShortDate(point.deadlineAt!)}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        if (point.resolutionSummary != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text('✓ ${point.resolutionSummary!}'),
        ],
        if (_feedback != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text(_feedback!),
        ],
        if (point.requiresAcknowledgement &&
            point.attentionReason == 'acknowledge' &&
            !widget.readOnly) ...[
          const SizedBox(height: MakoloSpacing.md),
          FilledButton(
            onPressed: _busy ? null : _acknowledge,
            child: Text(_busy ? 'En cours…' : 'Bien reçu'),
          ),
        ],
        if (point.canRespond && !widget.readOnly) ...[
          const SizedBox(height: MakoloSpacing.md),
          if (point.responseMode == 'boolean')
            Wrap(
              spacing: MakoloSpacing.sm,
              children: [
                OutlinedButton(
                  onPressed: _busy ? null : () => _submitResponse(true),
                  child: const Text('Oui'),
                ),
                OutlinedButton(
                  onPressed: _busy ? null : () => _submitResponse(false),
                  child: const Text('Non'),
                ),
              ],
            )
          else if (point.responseMode == 'single_choice')
            Wrap(
              spacing: MakoloSpacing.sm,
              runSpacing: MakoloSpacing.sm,
              children: [
                for (final option in point.options)
                  OutlinedButton(
                    onPressed: _busy ? null : () => _submitResponse(option.id),
                    child: Text(option.label),
                  ),
              ],
            )
          else if (point.responseMode == 'multiple_choice')
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: MakoloSpacing.sm,
                  runSpacing: MakoloSpacing.sm,
                  children: [
                    for (final option in point.options)
                      FilterChip(
                        label: Text(option.label),
                        selected: _choices.contains(option.id),
                        onSelected: _busy
                            ? null
                            : (selected) => setState(() {
                                if (selected) {
                                  _choices.add(option.id);
                                } else {
                                  _choices.remove(option.id);
                                }
                              }),
                      ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.sm),
                FilledButton(
                  onPressed: _busy || _choices.isEmpty
                      ? null
                      : () => _submitResponse(_choices.toList()),
                  child: Text(_busy ? 'Envoi…' : 'Répondre'),
                ),
              ],
            )
          else if (point.supportsInteractiveResponse)
            FilledButton(
              onPressed: _busy ? null : _respond,
              child: Text(_busy ? 'Envoi…' : point.responseActionLabel),
            ),
        ],
        if (point.kind == 'exchange' && point.canRespond && !widget.readOnly)
          const SizedBox.shrink(),
      ],
    );
    if (interactive || point.kind == 'poll' || point.kind == 'request') {
      return MakoloCard(child: body);
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.sm, MakoloSpacing.md,
        MakoloSpacing.sm, MakoloSpacing.md,
      ),
      child: body,
    );
  }
}

final Object _cancelledResponse = Object();

Future<Object?> _collectResponseValue(
  BuildContext context,
  _ConversationPoint point,
) async {
  switch (point.responseMode) {
    case 'boolean':
      return await showDialog<Object?>(
            context: context,
            builder: (context) => SimpleDialog(
              title: Text(point.title),
              children: [
                SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Oui'),
                ),
                SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Non'),
                ),
              ],
            ),
          ) ??
          _cancelledResponse;
    case 'single_choice':
      return await showDialog<Object?>(
            context: context,
            builder: (context) => SimpleDialog(
              title: Text(point.title),
              children: [
                for (final option in point.options)
                  SimpleDialogOption(
                    onPressed: () => Navigator.pop(context, option.id),
                    child: Text(option.label),
                  ),
              ],
            ),
          ) ??
          _cancelledResponse;
    case 'multiple_choice':
      final selected = <String>{};
      return await showDialog<Object?>(
            context: context,
            builder: (context) => StatefulBuilder(
              builder: (context, setDialogState) => AlertDialog(
                title: Text(point.title),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final option in point.options)
                        CheckboxListTile(
                          value: selected.contains(option.id),
                          title: Text(option.label),
                          onChanged: (checked) {
                            setDialogState(() {
                              if (checked == true) {
                                selected.add(option.id);
                              } else {
                                selected.remove(option.id);
                              }
                            });
                          },
                        ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, _cancelledResponse),
                    child: const Text('Annuler'),
                  ),
                  FilledButton(
                    onPressed: selected.isEmpty
                        ? null
                        : () => Navigator.pop(
                            context,
                            selected.toList(growable: false),
                          ),
                    child: const Text('Continuer'),
                  ),
                ],
              ),
            ),
          ) ??
          _cancelledResponse;
    case 'date':
      final date = await showDatePicker(
        context: context,
        firstDate: DateTime(1900),
        lastDate: DateTime(2200),
        initialDate: DateTime.now(),
      );
      if (date == null) return _cancelledResponse;
      return date.toIso8601String().split('T').first;
    case 'datetime':
      final date = await showDatePicker(
        context: context,
        firstDate: DateTime(1900),
        lastDate: DateTime(2200),
        initialDate: DateTime.now(),
      );
      if (date == null || !context.mounted) return _cancelledResponse;
      final time = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.now(),
      );
      if (time == null) return _cancelledResponse;
      return DateTime(
        date.year,
        date.month,
        date.day,
        time.hour,
        time.minute,
      ).toUtc().toIso8601String();
    case 'free_text':
    case 'number':
      final controller = TextEditingController();
      final result = await showDialog<Object?>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(point.title),
          content: TextField(
            controller: controller,
            autofocus: true,
            keyboardType: point.responseMode == 'number'
                ? const TextInputType.numberWithOptions(decimal: true)
                : TextInputType.multiline,
            minLines: 1,
            maxLines: point.responseMode == 'number' ? 1 : 5,
            decoration: InputDecoration(
              labelText: point.responseMode == 'number'
                  ? 'Valeur'
                  : 'Votre réponse',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, _cancelledResponse),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) Navigator.pop(context, value);
              },
              child: const Text('Envoyer'),
            ),
          ],
        ),
      );
      controller.dispose();
      return result ?? _cancelledResponse;
    default:
      return _cancelledResponse;
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
    this.purpose,
    this.latestResult,
    this.updatedAt,
    this.matchedPointId,
  });

  final String id;
  final String title;
  final String? lifecycle;
  final int attentionCount;
  final bool allClear;
  final String? contextLabel;
  final String? purpose;
  final String? latestResult;
  final DateTime? updatedAt;
  final String? matchedPointId;

  factory _ConversationSummary.fromMap(Map<String, dynamic> row) {
    final context = _map(row['context']);
    return _ConversationSummary(
      id: _string(row['id']) ?? '',
      title: _string(row['title']) ?? 'Conversation',
      lifecycle: MakoloHumanization.presentationLabel(
        _string(row['lifecycle']),
      ),
      attentionCount: row['attention_count'] is num
          ? (row['attention_count'] as num).toInt()
          : 0,
      allClear: row['all_clear'] == true,
      contextLabel: _string(context['label']),
      purpose: _string(row['purpose']),
      latestResult: _string(row['latest_result']),
      updatedAt: DateTime.tryParse(_string(row['updated_at']) ?? ''),
      matchedPointId: _string(row['matched_point_id']),
    );
  }

  static List<_ConversationSummary> fromProjection(
    StoredProjection? projection,
  ) => _maps(projection?.payload['results'])
      .map(_ConversationSummary.fromMap)
      .where((item) => item.id.isNotEmpty)
      .toList(growable: false);
}

class _ConversationDetail {
  const _ConversationDetail({
    required this.title,
    required this.points,
    required this.essential,
    required this.personalState,
    this.elsewhere = const [],
    this.focusedPoint,
    this.purpose,
    this.lifecycle,
    this.contextLabel,
  });

  final String title;
  final String? purpose;
  final String? lifecycle;
  final String? contextLabel;
  final List<_ConversationPoint> points;
  final List<_ConversationPoint> essential;
  final List<_ConversationPoint> elsewhere;
  final _ConversationPoint? focusedPoint;
  final _ConversationPersonalState personalState;

  factory _ConversationDetail.fromProjection(StoredProjection? projection) {
    if (projection == null) {
      return const _ConversationDetail(
        title: 'Conversation',
        points: [],
        essential: [],
        personalState: _ConversationPersonalState(),
      );
    }
    final payload = projection.payload;
    final context = _map(payload['context']);
    return _ConversationDetail(
      title: _string(payload['title']) ?? 'Conversation',
      purpose: _string(payload['purpose']),
      lifecycle: MakoloHumanization.presentationLabel(
        _string(payload['lifecycle']),
      ),
      contextLabel: _string(context['label']),
      points: _maps(payload['points'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      essential: _maps(payload['essential'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      elsewhere: _maps(payload['elsewhere'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      focusedPoint: _map(payload['focused_point']).isEmpty
          ? null
          : _ConversationPoint.fromMap(_map(payload['focused_point'])),
      personalState: _ConversationPersonalState.fromMap(
        _map(payload['personal_state']),
      ),
    );
  }
}

class _ConversationPersonalState {
  const _ConversationPersonalState({
    this.muted = false,
    this.hidden = false,
    this.archived = false,
    this.pinned = false,
    this.revisit = false,
  });

  final bool muted;
  final bool hidden;
  final bool archived;
  final bool pinned;
  final bool revisit;

  factory _ConversationPersonalState.fromMap(Map<String, dynamic> row) =>
      _ConversationPersonalState(
        muted: row['muted'] == true,
        hidden: row['hidden'] == true,
        archived: row['archived'] == true,
        pinned: row['pinned'] == true,
        revisit: row['revisit'] == true,
      );
}

class _ConversationOption {
  const _ConversationOption({required this.id, required this.label});

  final String id;
  final String label;

  factory _ConversationOption.fromMap(Map<String, dynamic> row) =>
      _ConversationOption(
        id: _string(row['id']) ?? '',
        label: _string(row['label']) ?? '',
      );
}

class _ConversationPoint {
  const _ConversationPoint({
    required this.id,
    required this.title,
    required this.responseMode,
    required this.lifecycle,
    required this.requiresAcknowledgement,
    required this.canRespond,
    required this.options,
    this.body,
    this.attentionReason,
    this.section,
    this.resolutionSummary,
    this.kind,
    this.importance,
    this.conversationId,
    this.opensAt,
    this.deadlineAt,
    this.validUntil,
    this.publishedAt,
    this.updatedAt,
  });

  final String id;
  final String title;
  final String responseMode;
  final String? body;
  final String? lifecycle;
  final bool requiresAcknowledgement;
  final bool canRespond;
  final List<_ConversationOption> options;
  final String? attentionReason;
  final String? section;
  final String? resolutionSummary;
  final String? kind;
  final String? importance;
  final String? conversationId;
  final DateTime? opensAt;
  final DateTime? deadlineAt;
  final DateTime? validUntil;
  final DateTime? publishedAt;
  final DateTime? updatedAt;

  bool get supportsInteractiveResponse => switch (responseMode) {
    'free_text' ||
    'boolean' ||
    'single_choice' ||
    'multiple_choice' ||
    'number' ||
    'date' ||
    'datetime' => true,
    _ => false,
  };

  String get responseActionLabel => switch (responseMode) {
    'boolean' => 'Confirmer',
    'single_choice' || 'multiple_choice' => 'Choisir',
    'date' || 'datetime' => 'Indiquer',
    _ => 'Répondre',
  };

  factory _ConversationPoint.fromMap(Map<String, dynamic> row) {
    return _ConversationPoint(
      id: _string(row['id']) ?? '',
      title: _string(row['title']) ?? 'Point',
      responseMode: _string(row['response_mode']) ?? 'none',
      body: _string(row['body']),
      lifecycle: MakoloHumanization.presentationLabel(
        _string(row['lifecycle']),
      ),
      requiresAcknowledgement: row['requires_acknowledgement'] == true,
      canRespond: row['can_respond'] == true,
      options: _maps(row['options'])
          .map(_ConversationOption.fromMap)
          .where((option) => option.id.isNotEmpty)
          .toList(growable: false),
      attentionReason: _string(row['attention_reason']),
      section: _string(row['section']),
      resolutionSummary: _string(row['resolution_summary']),
      kind: _string(row['kind']),
      importance: _string(row['importance']),
      conversationId: _string(row['conversation_id']),
      opensAt: DateTime.tryParse(_string(row['opens_at']) ?? ''),
      deadlineAt: DateTime.tryParse(_string(row['deadline_at']) ?? ''),
      validUntil: DateTime.tryParse(_string(row['valid_until']) ?? ''),
      publishedAt: DateTime.tryParse(_string(row['published_at']) ?? ''),
      updatedAt: DateTime.tryParse(_string(row['updated_at']) ?? ''),
    );
  }
}

class _ConversationInvitation {
  const _ConversationInvitation({
    required this.id,
    required this.conversationId,
    required this.status,
    this.expiresAt,
    this.createdAt,
  });

  final String id;
  final String conversationId;
  final String status;
  final DateTime? expiresAt;
  final DateTime? createdAt;

  bool get expired {
    final value = expiresAt;
    return status == 'expired' ||
        (value != null && !DateTime.now().isBefore(value));
  }

  static List<_ConversationInvitation> fromProjection(
    StoredProjection? projection,
  ) => _maps(projection?.payload['results'])
      .map(
        (row) => _ConversationInvitation(
          id: _string(row['id']) ?? '',
          conversationId: _string(row['conversation_id']) ?? '',
          status: _string(row['status']) ?? '',
          expiresAt: DateTime.tryParse(_string(row['expires_at']) ?? ''),
          createdAt: DateTime.tryParse(_string(row['created_at']) ?? ''),
        ),
      )
      .where((item) => item.id.isNotEmpty)
      .toList(growable: false);
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
