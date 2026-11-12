import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/interaction_primitives.dart';

import '../../data/local/profile_store.dart';
import '../../network/api_error.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'conversation_repository.dart';
import 'conversation_local_delivery.dart';
import 'conversation_list_tile.dart';
import 'conversation_details_screen.dart';
import 'conversation_composer.dart';
import 'conversation_point_presentation.dart';
import 'conversation_media_group.dart';
import 'conversation_exchange_sheet.dart';
import 'conversation_media_sheet.dart';

class ConversationListScreen extends StatefulWidget {
  const ConversationListScreen({
    super.key,
    required this.repository,
    required this.onOpen,
    this.onOpenPoint,
    this.spaceId,
  });

  final ConversationRepository repository;
  final void Function(String id) onOpen;
  final void Function(String id, String pointId)? onOpenPoint;

  /// Strict owner-scoped mode. A Space never becomes a chat participant.
  final String? spaceId;

  @override
  State<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends State<ConversationListScreen>
    with WidgetsBindingObserver {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;
  bool _attemptedRefresh = false;
  Future<Map<String, dynamic>>? _spaceRows;
  String _spaceSearch = '';
  bool _spaceEnsureBusy = false;
  String? _spaceEnsureError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (widget.spaceId == null) {
      unawaited(_acquireOrRefresh());
    } else {
      _loadSpaceRows();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    widget.repository.realtime?.foreground(state == AppLifecycleState.resumed);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void _loadSpaceRows() {
    final id = widget.spaceId;
    if (id == null) return;
    _spaceRows = widget.repository.contextDecision(kind: 'space', id: id);
  }

  void _refreshSpaceRows() => setState(_loadSpaceRows);

  Future<void> _ensureSpaceConversation() async {
    final id = widget.spaceId;
    if (id == null || _spaceEnsureBusy) return;
    setState(() {
      _spaceEnsureBusy = true;
      _spaceEnsureError = null;
    });
    try {
      final conversationId = await widget.repository.ensureContext(
        kind: 'space',
        id: id,
      );
      if (mounted && id == widget.spaceId) {
        widget.onOpen(conversationId);
      }
    } on Object {
      if (mounted && id == widget.spaceId) {
        setState(
          () => _spaceEnsureError =
              'Impossible d’ouvrir cet échange avec les droits actuels.',
        );
      }
    } finally {
      if (mounted) setState(() => _spaceEnsureBusy = false);
    }
  }

  @override
  void didUpdateWidget(covariant ConversationListScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.spaceId != widget.spaceId) {
      _requestedInitialRefresh = false;
      _attemptedRefresh = false;
      _refreshing = false;
      _spaceSearch = '';
      _spaceEnsureBusy = false;
      _spaceEnsureError = null;
      if (widget.spaceId == null) {
        _spaceRows = null;
        unawaited(_acquireOrRefresh());
      } else {
        _loadSpaceRows();
      }
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

  Future<void> _refreshInvitationsIfNeeded({
    bool force = false,
    bool propagateError = false,
  }) async {
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
              ) !=
              FreshnessState.fresh) {
        await repository.refreshInvitations();
      }
    } on Object {
      // Passive refresh remains discreet. Explicit refresh must tell its
      // caller that the current owner acquisition was not confirmed.
      if (propagateError) rethrow;
    }
  }

  Future<void> _openInvitations() async {
    unawaited(_refreshInvitationsIfNeeded());
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheetContext) => FractionallySizedBox(
        heightFactor: 0.85,
        child: _ConversationInvitationInbox(
          repository: widget.repository,
          onRefresh: () =>
              _refreshInvitationsIfNeeded(force: true, propagateError: true),
          onOpen: (id) {
            Navigator.of(sheetContext).pop();
            widget.onOpen(id);
          },
        ),
      ),
    );
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

  /// The same Conversations screen, but the owner selects rows by a
  /// verified Space context. Never read the personal cached inbox here:
  /// stale or unscoped results must not appear as collective access.
  Widget _spaceList(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Conversations'),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: _refreshSpaceRows,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    ),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _spaceRows,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MakoloErrorState(
            message: 'Conversations de cet Espace indisponibles.',
            onRetry: _refreshSpaceRows,
          );
        }
        if (!snapshot.hasData)
          return const MakoloLoadingState(
            label: 'Chargement des conversations de cet Espace…',
          );
        final response = snapshot.data!;
        final raw = response['results'];
        final rows = (raw is List ? raw : const <Object>[])
            .whereType<Map>()
            .map(
              (item) =>
                  item.map((key, value) => MapEntry(key.toString(), value)),
            )
            .map(_ConversationSummary.fromMap)
            .where((item) => item.id.isNotEmpty)
            .toList(growable: false);
        final canEnsure = response['can_ensure'] == true;
        final term = _spaceSearch.trim().toLowerCase();
        final visible = term.isEmpty
            ? rows
            : rows
                  .where(
                    (item) =>
                        item.title.toLowerCase().contains(term) ||
                        (item.purpose ?? '').toLowerCase().contains(term) ||
                        (item.contextLabel ?? '').toLowerCase().contains(term),
                  )
                  .toList(growable: false);
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 860),
            child: ListView(
              key: const Key('conversation-space-list-content'),
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.inner,
                vertical: MakoloSpacing.md,
              ),
              children: [
                Text(
                  'Échanges liés à cet Espace',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.sm),
                TextField(
                  key: const Key('conversation-space-search-field'),
                  decoration: const InputDecoration(
                    labelText: 'Rechercher',
                    hintText: 'Rechercher dans cet Espace…',
                    prefixIcon: Icon(Icons.search_rounded),
                  ),
                  onChanged: (value) => setState(() => _spaceSearch = value),
                ),
                const SizedBox(height: MakoloSpacing.md),
                if (visible.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      vertical: MakoloSpacing.lg,
                    ),
                    child: Text(
                      term.isEmpty
                          ? 'Aucune conversation accessible dans cet Espace.'
                          : 'Aucun résultat dans cet Espace.',
                    ),
                  )
                else
                  for (final item in visible) ...[
                    ConversationListTile(
                      key: Key('conversation-tile-${item.id}'),
                      title: item.title,
                      contextKind: item.contextKind,
                      subtitle: item.subtitle,
                      preview: item.preview,
                      previewKind: item.previewKind,
                      mediaKinds: item.mediaKinds,
                      publicImageUri: widget.repository.publicContextImageUri(
                        item.contextImageUrl,
                      ),
                      updatedAt: item.updatedAt,
                      attentionCount: item.attentionCount,
                      unreadCount: item.unreadCount,
                      onTap: () => widget.onOpen(item.id),
                    ),
                    const Divider(height: 1),
                  ],
                if (rows.isEmpty && canEnsure && term.isEmpty) ...[
                  const SizedBox(height: MakoloSpacing.md),
                  FilledButton.icon(
                    onPressed: _spaceEnsureBusy
                        ? null
                        : _ensureSpaceConversation,
                    icon: const Icon(Icons.forum_outlined),
                    label: Text(
                      _spaceEnsureBusy ? 'Ouverture…' : 'Commencer un échange',
                    ),
                  ),
                  if (_spaceEnsureError != null)
                    Text(
                      _spaceEnsureError!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                ],
              ],
            ),
          ),
        );
      },
    ),
  );

  @override
  Widget build(BuildContext context) {
    if (widget.spaceId != null) return _spaceList(context);
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
                  : source.lastErrorCode != null ||
                        (!available && _attemptedRefresh)
                  ? available
                        ? MakoloFailureCue.recoverable
                        : MakoloFailureCue.blocking
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: const Text('Conversations'),
                actions: [
                  StreamBuilder<StoredProjection?>(
                    stream: widget.repository.watchInvitations(),
                    builder: (context, snapshot) {
                      final count =
                          _ConversationInvitation.fromProjection(snapshot.data)
                              .where((invitation) => !invitation.expired)
                              .length +
                          _ConversationPendingRow.fromProjection(
                            snapshot.data,
                            'join_requests_to_decide',
                          ).length;
                      return IconButton(
                        key: const Key('conversation-invitations-open'),
                        tooltip: 'Invitations reçues',
                        onPressed: _openInvitations,
                        icon: count > 0
                            ? Badge.count(
                                count: count,
                                child: const Icon(Icons.mail_outline_rounded),
                              )
                            : const Icon(Icons.mail_outline_rounded),
                      );
                    },
                  ),
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              // Network status is already represented by the thin shell cue.
              // Never replace a cached inbox with a transport-error tutorial.
              body:
                  (source.lastErrorCode != 'permission_denied' &&
                      source.lastErrorCode != 'not_found' &&
                      (available || (_attemptedRefresh && !_refreshing)))
                  ? _ConversationListBody(
                      repository: widget.repository,
                      items: items,
                      onOpen: widget.onOpen,
                      onOpenPoint: widget.onOpenPoint,
                    )
                  : MakoloSurfaceStateView(
                      state: surface,
                      initialLoading: const MakoloLoadingState(
                        label: 'Chargement des conversations…',
                      ),
                      blockingErrorMessage:
                          'Impossible de charger vos conversations.',
                      onRetry: _refresh,
                      content: _ConversationListBody(
                        repository: widget.repository,
                        items: items,
                        onOpen: widget.onOpen,
                        onOpenPoint: widget.onOpenPoint,
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
    this.onOpenPoint,
  });

  final ConversationRepository repository;
  final List<_ConversationSummary> items;
  final void Function(String id) onOpen;
  final void Function(String id, String pointId)? onOpenPoint;

  @override
  State<_ConversationListBody> createState() => _ConversationListBodyState();
}

class _ConversationListBodyState extends State<_ConversationListBody> {
  String _query = '';
  Timer? _debounce;
  int _searchGeneration = 0;
  bool _searching = false;
  List<_ConversationSummary> _remote = const [];
  List<_ConversationSummary> _archived = const [];
  String _tab = 'all';
  bool _archiveLoading = false;

  Future<void> _loadArchive() async {
    if (_archiveLoading) return;
    final repository = widget.repository;
    setState(() {
      _archiveLoading = true;
    });
    try {
      final local = await repository.readArchived();
      if (mounted && widget.repository == repository && local != null) {
        setState(() {
          _archived = _ConversationSummary.fromProjection(local);
        });
      }
      await repository.refreshArchived();
      final acquired = await repository.readArchived();
      if (!mounted || widget.repository != repository) return;
      setState(() {
        _archived = _ConversationSummary.fromProjection(acquired);
      });
    } on MakoloApiError catch (error) {
      if (mounted && widget.repository == repository) {
        setState(() {
          if (error.statusCode == 403 || error.statusCode == 404) {
            _archived = const [];
          }
        });
      }
    } on Object {
      // Preserve the archived conversations already read from the device.
    } finally {
      if (mounted && widget.repository == repository) {
        setState(() => _archiveLoading = false);
      }
    }
  }

  void _setTab(String tab) {
    if (_tab == tab) return;
    _debounce?.cancel();
    _searchGeneration++;
    setState(() {
      _tab = tab;
      _remote = const [];
      _searching = false;
    });
    if (tab == 'archived') unawaited(_loadArchive());
    if (_query.isNotEmpty) _scheduleSearch(_query);
  }

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
      _archived = const [];
      _tab = 'all';
      _archiveLoading = false;
      _searching = false;
      if (_query.trim().isNotEmpty) _scheduleSearch(_query);
    }
  }

  void _scheduleSearch(String query) {
    _debounce?.cancel();
    final generation = ++_searchGeneration;
    setState(() {
      _query = query;
      _remote = const [];
      _searching = query.trim().isNotEmpty;
    });
    if (!_searching) return;
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      try {
        final results = await widget.repository.searchConversations(
          query,
          tab: _tab,
        );
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
        });
      }
    });
  }

  List<_ConversationSummary> _matchingRows() {
    final available = _tab == 'archived'
        ? _archived
        : _tab == 'for-me'
        ? widget.items.where((row) => row.attentionCount > 0).toList()
        : widget.items;
    final normalized = _query.trim().toLowerCase();
    if (normalized.isEmpty) return available;
    final known = <String, _ConversationSummary>{};
    for (final item in available) {
      if (item.title.toLowerCase().contains(normalized) ||
          (item.purpose ?? '').toLowerCase().contains(normalized) ||
          (item.contextLabel ?? '').toLowerCase().contains(normalized) ||
          (item.latestResult ?? '').toLowerCase().contains(normalized)) {
        known[item.id] = item;
      }
    }
    // Owner results win for their focused Point, without duplicating a row.
    // Search is already scoped to 'for-me' by the owner. Relying on the
    // first cached list page here would silently lose valid later matches.
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
            return Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 860),
                child: ListView(
                  key: const Key('conversation-list-content'),
                  padding: const EdgeInsets.symmetric(
                    horizontal: MakoloSpacing.inner,
                    vertical: MakoloSpacing.md,
                  ),
                  children: [
                    TextField(
                      key: const Key('conversation-search-field'),
                      onChanged: _scheduleSearch,
                      maxLength: 120,
                      textInputAction: TextInputAction.search,
                      decoration: InputDecoration(
                        labelText: 'Rechercher',
                        counterText: '',
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
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  ),
                                ),
                              )
                            : null,
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Wrap(
                      spacing: MakoloSpacing.sm,
                      runSpacing: MakoloSpacing.xs,
                      children: [
                        ChoiceChip(
                          key: const Key('conversation-tab-all'),
                          label: const Text('Toutes'),
                          selected: _tab == 'all',
                          onSelected: (_) => _setTab('all'),
                        ),
                        ChoiceChip(
                          key: const Key('conversation-tab-for-me'),
                          label: const Text('À traiter'),
                          selected: _tab == 'for-me',
                          onSelected: (_) => _setTab('for-me'),
                        ),
                        ChoiceChip(
                          key: const Key('conversation-tab-archived'),
                          label: const Text('Archives'),
                          selected: _tab == 'archived',
                          onSelected: (_) => _setTab('archived'),
                        ),
                      ],
                    ),
                    if (_archiveLoading && _tab == 'archived')
                      const Padding(
                        padding: EdgeInsets.only(top: 8),
                        child: LinearProgressIndicator(minHeight: 2),
                      ),

                    if (invitations.isNotEmpty && _query.isEmpty) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      Text(
                        'Invitations',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
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
                        padding: const EdgeInsets.symmetric(
                          vertical: MakoloSpacing.lg,
                        ),
                        child: Text(
                          _query.trim().isEmpty
                              ? (_tab == 'archived'
                                    ? 'Aucune archive disponible.'
                                    : 'Aucune conversation à afficher.')
                              : _searching
                              ? 'Recherche…'
                              : 'Aucun résultat.',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      )
                    else
                      for (final item in filtered) ...[
                        ConversationListTile(
                          key: Key('conversation-tile-${item.id}'),
                          title: item.title,
                          contextKind: item.contextKind,
                          subtitle: item.subtitle,
                          preview: item.preview,
                          previewKind: item.previewKind,
                          mediaKinds: item.mediaKinds,
                          publicImageUri: widget.repository
                              .publicContextImageUri(item.contextImageUrl),
                          updatedAt: item.updatedAt,
                          attentionCount: item.attentionCount,
                          unreadCount: item.unreadCount,
                          archived: _tab == 'archived',
                          onTap: () => _open(item),
                        ),
                        const Divider(height: 1),
                      ],
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

class _ConversationInvitationInbox extends StatefulWidget {
  const _ConversationInvitationInbox({
    required this.repository,
    required this.onRefresh,
    required this.onOpen,
  });

  final ConversationRepository repository;
  final Future<void> Function() onRefresh;
  final void Function(String id) onOpen;

  @override
  State<_ConversationInvitationInbox> createState() =>
      _ConversationInvitationInboxState();
}

class _ConversationInvitationInboxState
    extends State<_ConversationInvitationInbox> {
  bool _refreshing = false;
  String? _refreshError;

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() {
      _refreshing = true;
      _refreshError = null;
    });
    try {
      await widget.onRefresh();
    } on Object {
      if (mounted) {
        setState(
          () => _refreshError = 'Invitations non actualisées. Vos informations conservées restent disponibles.',
        );
      }
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Invitations et demandes'),
        actions: [
          IconButton(
            tooltip: 'Actualiser les invitations',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchInvitations(),
        builder: (context, snapshot) {
          final invitations = _ConversationInvitation.fromProjection(
            snapshot.data,
          );
          final toDecide = _ConversationPendingRow.fromProjection(
            snapshot.data,
            'join_requests_to_decide',
          );
          final sent = _ConversationPendingRow.fromProjection(
            snapshot.data,
            'sent_results',
          );
          final mine = _ConversationPendingRow.fromProjection(
            snapshot.data,
            'my_join_requests',
          );
          return ListView(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            children: [
              if (_refreshing) const LinearProgressIndicator(minHeight: 2),
              if (_refreshError != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                  child: Text(
                    _refreshError!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (snapshot.data == null)
                const Text(
                  'Invitations non encore disponibles sur cet appareil.',
                )
              else if (invitations.isEmpty &&
                  toDecide.isEmpty &&
                  sent.isEmpty &&
                  mine.isEmpty)
                const Text('Aucune invitation ou demande en attente.'),
              if (invitations.isNotEmpty) ...[
                Text(
                  'Invitations reçues',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.sm),
                for (final invitation in invitations) ...[
                  _ConversationInvitationCard(
                    key: Key('conversation-received-${invitation.id}'),
                    invitation: invitation,
                    repository: widget.repository,
                    onOpen: widget.onOpen,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
              if (toDecide.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  'Demandes à examiner',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.sm),
                for (final row in toDecide) ...[
                  _ConversationPendingActionCard(
                    key: Key('conversation-request-${row.id}'),
                    row: row,
                    repository: widget.repository,
                    isJoinRequest: true,
                    onOpen: widget.onOpen,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
              if (sent.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  'Invitations envoyées',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.sm),
                for (final row in sent) ...[
                  _ConversationPendingActionCard(
                    key: Key('conversation-sent-${row.id}'),
                    row: row,
                    repository: widget.repository,
                    isJoinRequest: false,
                    onOpen: widget.onOpen,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
              if (mine.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  'Mes demandes d’entrée',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.sm),
                for (final row in mine) ...[
                  _ConversationPersonalJoinCard(
                    key: Key('conversation-my-request-${row.id}'),
                    row: row,
                    repository: widget.repository,
                    onOpen: widget.onOpen,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
              if (snapshot.data?.payload['more_received'] == true ||
                  snapshot.data?.payload['more_collective'] == true ||
                  snapshot.data?.payload['more_sent'] == true ||
                  snapshot.data?.payload['more_join_requests'] == true ||
                  snapshot.data?.payload['more_my_requests'] == true)
                const Padding(
                  padding: EdgeInsets.only(top: MakoloSpacing.sm),
                  child: Text(
                    'La liste affichée est partielle. Actualisez ou consultez les Conversations concernées.',
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _ConversationPersonalJoinCard extends StatefulWidget {
  const _ConversationPersonalJoinCard({
    super.key,
    required this.row,
    required this.repository,
    required this.onOpen,
  });

  final _ConversationPendingRow row;
  final ConversationRepository repository;
  final void Function(String id) onOpen;

  @override
  State<_ConversationPersonalJoinCard> createState() =>
      _ConversationPersonalJoinCardState();
}

class _ConversationPersonalJoinCardState
    extends State<_ConversationPersonalJoinCard> {
  bool _busy = false;
  bool _confirmed = false;
  String? _error;

  Future<void> _withdraw() async {
    if (_busy || _confirmed) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.withdrawJoinRequest(widget.row.id);
      if (mounted) setState(() => _confirmed = true);
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Retrait non confirmé. Actualisez avant de réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => MakoloCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _confirmed ? 'Demande retirée' : 'Demande en attente de décision',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        if (_error != null)
          Text(
            _error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        const SizedBox(height: MakoloSpacing.sm),
        Wrap(
          spacing: MakoloSpacing.sm,
          runSpacing: MakoloSpacing.xs,
          children: [
            if (!_confirmed && widget.row.conversationId != null)
              MakoloActionButton(
                label: 'Voir ma demande',
                onPressed: () => widget.onOpen(widget.row.conversationId!),
                appearance: MakoloActionAppearance.quiet,
              ),
            if (!_confirmed)
              MakoloActionButton(
                label: _busy ? 'Retrait en cours…' : 'Retirer ma demande',
                onPressed: _busy ? null : _withdraw,
                appearance: MakoloActionAppearance.secondary,
                busy: _busy,
              ),
          ],
        ),
      ],
    ),
  );
}

class _ConversationPendingRow {
  const _ConversationPendingRow({
    required this.id,
    required this.kind,
    this.conversationId,
    this.identifier,
    this.canApprove = true,
  });

  final String id;
  final String kind;
  final String? conversationId;
  final String? identifier;
  final bool canApprove;

  static List<_ConversationPendingRow> fromProjection(
    StoredProjection? projection,
    String section,
  ) {
    return [
      for (final row in _maps(projection?.payload[section]))
        if (_string(row['id']) != null)
          _ConversationPendingRow(
            id: _string(row['id'])!,
            kind: _string(row['kind']) ?? '',
            conversationId: _string(row['conversation_id']),
            identifier: _string(row['identifier']),
            canApprove: row['can_approve'] != false,
          ),
    ];
  }
}

class _ConversationPendingActionCard extends StatefulWidget {
  const _ConversationPendingActionCard({
    super.key,
    required this.row,
    required this.repository,
    required this.isJoinRequest,
    required this.onOpen,
  });

  final _ConversationPendingRow row;
  final ConversationRepository repository;
  final bool isJoinRequest;
  final void Function(String id) onOpen;

  @override
  State<_ConversationPendingActionCard> createState() =>
      _ConversationPendingActionCardState();
}

class _ConversationPendingActionCardState
    extends State<_ConversationPendingActionCard> {
  bool _busy = false;
  bool _confirmed = false;
  String? _error;

  Future<void> _decide(bool accept) async {
    final id = widget.row.conversationId;
    if (_busy || _confirmed || id == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (widget.isJoinRequest) {
        await widget.repository.decideJoinRequest(
          conversationId: id,
          requestId: widget.row.id,
          approve: accept,
        );
      } else {
        await widget.repository.manageConversationParticipant(
          conversationId: id,
          operation: widget.row.kind == 'profile' ? 'cancel' : 'revoke',
          resourceId: widget.row.id,
        );
      }
      if (mounted) setState(() => _confirmed = true);
    } on Object {
      if (mounted) {
        setState(
          () =>
              _error = 'Décision non confirmée. Actualisez avant de réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
    final label = row.identifier == null
        ? 'Demande d’entrée'
        : row.kind == 'profile' || widget.isJoinRequest
        ? '@${row.identifier}'
        : row.identifier!;
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: MakoloSpacing.xs),
          Text(
            widget.isJoinRequest
                ? 'Demande d’entrée en attente'
                : 'Invitation en attente d’acceptation',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (widget.isJoinRequest && !row.canApprove)
            const Text(
              'Cette entrée n’est plus éligible. Vous pouvez la refuser.',
            ),
          if (_confirmed) const Text('Décision confirmée.'),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          const SizedBox(height: MakoloSpacing.sm),
          Wrap(
            spacing: MakoloSpacing.sm,
            runSpacing: MakoloSpacing.xs,
            children: [
              if (row.conversationId != null)
                MakoloActionButton(
                  label: 'Ouvrir la conversation',
                  onPressed: () => widget.onOpen(row.conversationId!),
                  appearance: MakoloActionAppearance.quiet,
                ),
              if (!_confirmed && widget.isJoinRequest) ...[
                MakoloActionButton(
                  label: 'Refuser',
                  onPressed: _busy ? null : () => _decide(false),
                  appearance: MakoloActionAppearance.secondary,
                ),
                if (row.canApprove)
                  MakoloActionButton(
                    label: _busy ? 'En cours…' : 'Accepter',
                    onPressed: _busy ? null : () => _decide(true),
                    appearance: MakoloActionAppearance.primary,
                    busy: _busy,
                  ),
              ],
              if (!_confirmed && !widget.isJoinRequest)
                MakoloActionButton(
                  label: 'Annuler l’invitation',
                  onPressed: _busy ? null : () => _decide(false),
                  appearance: MakoloActionAppearance.secondary,
                  busy: _busy,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ConversationInvitationCard extends StatefulWidget {
  const _ConversationInvitationCard({
    super.key,
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
    if (_busy ||
        widget.invitation.status != 'pending' ||
        widget.invitation.expired ||
        (accept && !widget.invitation.canAccept))
      return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final conversationId = widget.invitation.collective
          ? await widget.repository
                .decideCollectiveInvitation(
                  accessId: widget.invitation.id,
                  accept: accept,
                )
                .then((_) => widget.invitation.conversationId)
          : await widget.repository.respondToInvitation(
              invitationId: widget.invitation.id,
              accept: accept,
            );
      if (!mounted) return;
      if (accept && conversationId != null && !widget.invitation.collective) {
        widget.onOpen(conversationId);
      }
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
            widget.invitation.collective
                ? 'Invitation pour ${widget.invitation.label ?? 'un collectif'}'
                : 'Invitation à rejoindre une coordination',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          if (widget.invitation.invitedBy != null)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(
                'Envoyée par @${widget.invitation.invitedBy}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          if (widget.invitation.collective)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(
                'Seul un responsable autorisé peut accepter. '
                'Les membres actuels conservent leur appartenance canonique. '
                '${widget.invitation.identifier ?? ''}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          if (!widget.invitation.canAccept)
            const Padding(
              padding: EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(
                'Cette invitation ne peut plus être acceptée. Vous pouvez la refuser.',
              ),
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
              MakoloActionButton(
                label: 'Refuser',
                onPressed:
                    _busy ||
                        widget.invitation.status != 'pending' ||
                        widget.invitation.expired
                    ? null
                    : () => _respond(false),
                appearance: MakoloActionAppearance.secondary,
              ),
              MakoloActionButton(
                label: _busy ? 'En cours…' : 'Accepter',
                onPressed:
                    _busy ||
                        !widget.invitation.canAccept ||
                        widget.invitation.status != 'pending' ||
                        widget.invitation.expired
                    ? null
                    : () => _respond(true),
                appearance: MakoloActionAppearance.primary,
                busy: _busy,
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
    this.onOpenFormRequest,
    this.onOpenHistory,
    this.onOpenDetails,
    this.onOpenRelatedPoint,
  });

  final String id;
  final ConversationRepository repository;
  final String? representedSpaceId;
  final String? focusPointId;
  final Future<void> Function(String requestId)? onOpenFormRequest;
  final VoidCallback? onOpenHistory;
  final VoidCallback? onOpenDetails;
  final ValueChanged<String>? onOpenRelatedPoint;

  @override
  State<ConversationDetailScreen> createState() =>
      _ConversationDetailScreenState();
}

class _ConversationDetailScreenState extends State<ConversationDetailScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  final ScrollController _timelineScroll = ScrollController();
  bool _timelinePositioned = false;
  bool _nearLatest = true;
  bool _newMessagesAvailable = false;
  String? _lastTimelinePointId;
  String? _lastReceivedPointId;
  final List<_ConversationPoint> _olderPoints = [];
  String? _olderCursor;
  String? _olderBaseSignature;
  String? _activeTimelineSignature;
  bool _olderLoaded = false;
  bool _loadingOlder = false;
  String? _olderError;
  final Set<String> _expandedCompletedGroups = {};

  final GlobalKey _pointFocusKey = GlobalKey();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;
  bool _attemptedRefresh = false;
  String? _handledFocus;
  String? _justPublishedPointId;
  Map<String, dynamic> _activeComposer = const {};

  Future<void> _openResponseMedia(_ConversationPoint point, String mode) async {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => ConversationMediaSheet(
        mode: mode,
        responsePointId: point.id,
        repository: widget.repository,
        conversationId: widget.id,
        capabilities: _activeComposer,
        representedSpaceId: widget.representedSpaceId,
        onPublished: (pointId) {
          Navigator.of(sheetContext).pop();
          _afterPublish(pointId);
        },
      ),
    );
  }

  Future<void> _openExchange(_ConversationPoint point) async {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) => FractionallySizedBox(
        heightFactor: 0.92,
        child: ConversationExchangeSheet(
          repository: widget.repository,
          conversationId: widget.id,
          pointId: point.id,
          title: point.title,
          canRespond: point.canRespond,
          capabilities: _activeComposer,
          representedSpaceId: widget.representedSpaceId,
          onPublished: _afterPublish,
        ),
      ),
    );
  }

  void _afterPublish(String pointId) {
    setState(() {
      _justPublishedPointId = pointId;
      _handledFocus = null;
    });
    // Publication was confirmed by the owner. The normal detail groups may
    // omit this Point, so explicitly reacquire its authorized focus projection.
    unawaited(_refreshPublishedFocus(pointId));
  }

  Future<void> _refreshPublishedFocus(String pointId) async {
    final repository = widget.repository;
    final conversationId = widget.id;
    try {
      await repository.refreshDetail(conversationId, focusPointId: pointId);
    } on Object {
      if (!mounted ||
          widget.repository != repository ||
          widget.id != conversationId ||
          _focusedPointId != pointId) {
        return;
      }
      // The owner already accepted this Point. Keep local content readable;
      // the next acquisition reconciles the projection silently.
    }
  }

  String? get _focusedPointId =>
      _attentionFocusedId ?? _justPublishedPointId ?? widget.focusPointId;
  String? _attentionFocusedId;

  void _openAttentionPoint(String pointId) {
    if (pointId.isEmpty) return;
    setState(() {
      _attentionFocusedId = pointId;
      _handledFocus = null;
    });
    unawaited(_refreshPublishedFocus(pointId));
  }

  Widget _attentionLens(BuildContext context, Map<String, dynamic> raw) {
    final focus = _map(raw);
    final count = focus['action_count'] is num
        ? (focus['action_count'] as num).toInt()
        : 0;
    final mine = _maps(focus['for_me']);
    final decisions = _maps(focus['to_resolve']);
    final knowledge = _maps(focus['to_know']);
    if (count == 0 && knowledge.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    String subtitleFor(Map<String, dynamic> item) {
      final reason = item['reason_label']?.toString() ?? '';
      final raw = item['deadline_at']?.toString();
      final date = raw == null ? null : DateTime.tryParse(raw)?.toLocal();
      if (date == null) return reason;
      final local = MaterialLocalizations.of(context);
      final deadline =
          '${local.formatShortDate(date)} '
          '${local.formatTimeOfDay(TimeOfDay.fromDateTime(date), alwaysUse24HourFormat: true)}';
      return '$reason · Échéance : $deadline';
    }

    Widget group(String name, List<Map<String, dynamic>> entries) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 3),
          child: Text(
            '$name · ${entries.length}',
            style: theme.textTheme.labelLarge,
          ),
        ),
        for (final item in entries)
          ListTile(
            dense: true,
            key: Key('conversation-attention-${item['id']}'),
            title: Text(
              item['label']?.toString() ?? 'Point',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(subtitleFor(item)),
            trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 14),
            onTap: () => _openAttentionPoint(item['id']?.toString() ?? ''),
          ),
      ],
    );
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      child: Card(
        margin: EdgeInsets.zero,
        child: ExpansionTile(
          key: const PageStorageKey('conversation-attention-lens'),
          leading: const Icon(Icons.fact_check_outlined),
          title: Text(
            count > 0 ? 'À présent · $count à traiter' : 'À présent · à savoir',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: knowledge.isNotEmpty
              ? Text(
                  '${knowledge.length} information${knowledge.length > 1 ? 's' : ''} utile${knowledge.length > 1 ? 's' : ''}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                )
              : null,
          children: [
            ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.sizeOf(context).height * 0.38,
              ),
              child: ListView(
                // The ExpansionTile stores a bool under its PageStorageKey.
                // Give this nested scrollable a separate slot for its double.
                key: const PageStorageKey('conversation-attention-scroll'),
                shrinkWrap: true,
                children: [
                  group('Pour moi', mine),
                  group('À régler', decisions),
                  group('À savoir', knowledge),
                  if (focus['more_actions'] == true)
                    const Padding(
                      padding: EdgeInsets.all(16),
                      child: Text(
                        'D’autres actions restent accessibles dans le fil '
                        'et dans l’historique de la conversation.',
                      ),
                    ),
                  const SizedBox(height: 8),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _timelineScroll.addListener(_trackTimelinePosition);
    unawaited(_acquireOrRefresh());
  }

  @override
  void dispose() {
    _timelineScroll.dispose();
    super.dispose();
  }

  void _trackTimelinePosition() {
    if (!_timelineScroll.hasClients) return;
    _nearLatest = _timelineScroll.position.extentAfter < 120;
    if (_nearLatest && _newMessagesAvailable) {
      setState(() => _newMessagesAvailable = false);
    }
  }

  void _showLatestMessages() {
    if (!_timelineScroll.hasClients) return;
    _timelineScroll.animateTo(
      _timelineScroll.position.maxScrollExtent,
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOut,
    );
    setState(() => _newMessagesAvailable = false);
  }

  void _positionTimeline(
    List<_ConversationTimelineEntry> entries,
    List<ConversationOutgoing> outgoing,
  ) {
    if ((entries.isEmpty && outgoing.isEmpty) || _focusedPointId != null) {
      return;
    }
    final lastPublished = entries.isNotEmpty
        ? entries.last.point.publishedAt ?? entries.last.point.updatedAt
        : null;
    final mostRecentPending = outgoing.isEmpty
        ? null
        : (outgoing.toList()
                ..sort((a, b) => a.observedAt.compareTo(b.observedAt)))
              .last;
    final latestId =
        mostRecentPending != null &&
            (lastPublished == null ||
                !mostRecentPending.observedAt.isBefore(lastPublished))
        ? mostRecentPending.reference
        : entries.last.point.id;
    final receivedId = entries.isEmpty ? null : entries.last.point.id;
    final hasNewMessages =
        _timelinePositioned &&
        _lastReceivedPointId != null &&
        receivedId != null &&
        _lastReceivedPointId != receivedId &&
        !_nearLatest;
    _lastReceivedPointId = receivedId;
    final shouldFollow =
        !_timelinePositioned ||
        (_lastTimelinePointId != latestId && _nearLatest);
    _timelinePositioned = true;
    _lastTimelinePointId = latestId;
    if (hasNewMessages && !_newMessagesAvailable) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !_nearLatest && !_newMessagesAvailable) {
          setState(() => _newMessagesAvailable = true);
        }
      });
    }
    if (!shouldFollow) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_timelineScroll.hasClients || _focusedPointId != null) {
        return;
      }
      _timelineScroll.jumpTo(_timelineScroll.position.maxScrollExtent);
    });
  }

  @override
  void didUpdateWidget(covariant ConversationDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.id != widget.id ||
        oldWidget.repository != widget.repository ||
        oldWidget.focusPointId != widget.focusPointId) {
      if (oldWidget.id != widget.id ||
          oldWidget.repository != widget.repository) {
        _timelinePositioned = false;
        _nearLatest = true;
        _newMessagesAvailable = false;
        _lastTimelinePointId = null;
        _lastReceivedPointId = null;
        _olderPoints.clear();
        _olderCursor = null;
        _olderBaseSignature = null;
        _activeTimelineSignature = null;
        _olderLoaded = false;
        _loadingOlder = false;
        _olderError = null;
        _expandedCompletedGroups.clear();
        _attentionFocusedId = null;
        if (_timelineScroll.hasClients) _timelineScroll.jumpTo(0);
      }
      _handledFocus = null;
      _justPublishedPointId = null;
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
      if (!mounted || repository != widget.repository || id != widget.id) {
        return;
      }
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
      await repository.refreshDetail(id, focusPointId: _focusedPointId);
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
        const SnackBar(content: Text('Modification non confirmée.')),
      );
    }
  }

  Widget _pointWidget(_ConversationPoint point, {bool readOnly = false}) {
    final focused = point.id == _focusedPointId;
    return Padding(
      key: focused ? _pointFocusKey : ValueKey('point-${point.id}'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: _PointCard(
        point: point,
        repository: widget.repository,
        conversationId: widget.id,
        representedSpaceId: widget.representedSpaceId,
        readOnly: readOnly,
        onOpenFormRequest: widget.onOpenFormRequest,
        onOpenExchange: () => _openExchange(point),
        onRespondWithMedia: (mode) => _openResponseMedia(point, mode),
        onOpenRelatedPoint: widget.onOpenRelatedPoint,
      ),
    );
  }

  String _timelineSignature(_ConversationDetail detail) {
    if (!detail.hasTimeline) return '';
    return [
      detail.timelineNextCursor ?? '',
      for (final point in detail.timeline)
        '${point.id}:${point.updatedAt?.toIso8601String() ?? ''}:'
            '${point.lifecycle ?? ''}:${point.timelineCompact}:'
            '${point.responseStatus['responded'] == true}',
    ].join('|');
  }

  String? _olderAvailableCursor(_ConversationDetail detail) {
    if (!detail.hasTimeline) return null;
    final signature = _timelineSignature(detail);
    return _olderLoaded && _olderBaseSignature == signature
        ? _olderCursor
        : detail.timelineNextCursor;
  }

  Future<void> _loadOlderPoints(_ConversationDetail detail) async {
    if (_loadingOlder || !detail.hasTimeline) return;
    final signature = _timelineSignature(detail);
    final cursor = _olderAvailableCursor(detail);
    if (cursor == null || cursor.isEmpty) return;
    final previousMax = _timelineScroll.hasClients
        ? _timelineScroll.position.maxScrollExtent
        : 0.0;
    final previousOffset = _timelineScroll.hasClients
        ? _timelineScroll.offset
        : 0.0;
    setState(() {
      _loadingOlder = true;
      _olderError = null;
    });
    try {
      final result = await widget.repository.pointDepth(
        conversationId: widget.id,
        section: 'all',
        cursor: cursor,
        limit: 40,
      );
      if (!mounted || _activeTimelineSignature != signature) return;
      final older = _maps(result['results'])
          .map(_ConversationPoint.fromMap)
          .where((point) => point.id.isNotEmpty)
          .toList(growable: false);
      setState(() {
        if (!_olderLoaded || _olderBaseSignature != signature) {
          _olderPoints.clear();
        }
        final known = {
          for (final point in _olderPoints) point.id,
          for (final point in detail.timeline) point.id,
        };
        for (final point in older) {
          if (known.add(point.id)) _olderPoints.add(point);
        }
        _olderLoaded = true;
        _olderBaseSignature = signature;
        _olderCursor = _string(result['next_cursor']);
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || !_timelineScroll.hasClients) return;
        final delta = _timelineScroll.position.maxScrollExtent - previousMax;
        final target = (previousOffset + delta)
            .clamp(
              _timelineScroll.position.minScrollExtent,
              _timelineScroll.position.maxScrollExtent,
            )
            .toDouble();
        _timelineScroll.jumpTo(target);
      });
    } on Object {
      if (mounted) {
        setState(
          () => _olderError = 'Impossible de charger les Points précédents. Vous pouvez réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _loadingOlder = false);
    }
  }

  // Preserve owner-selected read-only behavior while moving the presentation
  // from administrative sections to one chronological conversation timeline.
  List<_ConversationTimelineEntry> _timelineEntries(
    _ConversationDetail detail,
  ) {
    final entries = <_ConversationTimelineEntry>[];
    final seen = <String>{};
    void add(Iterable<_ConversationPoint> points, {required bool readOnly}) {
      for (final point in points) {
        if (point.id.isNotEmpty && seen.add(point.id)) {
          entries.add(
            _ConversationTimelineEntry(
              point: point,
              readOnly: readOnly,
              order: entries.length,
            ),
          );
        }
      }
    }

    if (detail.hasTimeline) {
      // The server supplied a profile-scoped, cursor-bounded true chronology.
      // Never rebuild it from priority / attention sections again.
      if (_olderLoaded && _olderBaseSignature == _timelineSignature(detail)) {
        add(_olderPoints, readOnly: false);
      }
      add(detail.timeline, readOnly: false);
    } else {
      // Compatibility with offline projections acquired before Lot 4.
      add(
        detail.points.where(
          (point) =>
              point.section == 'pour_moi' || point.attentionReason == 'resolve',
        ),
        readOnly: false,
      );
      add(
        detail.points.where(
          (point) =>
              point.section != 'pour_moi' && point.attentionReason != 'resolve',
        ),
        readOnly: true,
      );
      add(detail.essential, readOnly: true);
      add(detail.elsewhere, readOnly: true);
    }

    // An older focused Point is shown in a separate targeted panel, not
    // falsely inserted into a recent page with intervening history missing.
    final focus = detail.focusedPoint;
    if (!detail.hasTimeline && focus != null) {
      add([focus], readOnly: false);
    }
    entries.sort((a, b) {
      final left = a.point.publishedAt ?? a.point.updatedAt;
      final right = b.point.publishedAt ?? b.point.updatedAt;
      if (left != null && right != null) {
        final dateOrder = left.compareTo(right);
        if (dateOrder != 0) return dateOrder;
      } else if (left != null) {
        return 1;
      } else if (right != null) {
        return -1;
      }
      // UUID order is the server's keyset tie-breaker, not priority order.
      final byId = a.point.id.compareTo(b.point.id);
      return byId != 0 ? byId : a.order.compareTo(b.order);
    });
    return entries;
  }

  Widget _completedTimelineGroup(
    BuildContext context,
    List<_ConversationTimelineEntry> entries,
  ) {
    final first = entries.first.point;
    final last = entries.last.point;
    final groupId = '${first.id}-${last.id}';
    final focused = entries.any((entry) => entry.point.id == _focusedPointId);
    final expanded = focused || _expandedCompletedGroups.contains(groupId);
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    return Padding(
      key: Key('conversation-completed-$groupId'),
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.inner,
        0,
        MakoloSpacing.inner,
        MakoloSpacing.sm,
      ),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              button: true,
              label: expanded
                  ? 'Masquer ${entries.length} Point(s) terminés'
                  : 'Afficher ${entries.length} Point(s) terminés',
              child: InkWell(
                key: Key('conversation-completed-toggle-$groupId'),
                borderRadius: BorderRadius.circular(16),
                onTap: () => setState(() {
                  if (expanded && !focused) {
                    _expandedCompletedGroups.remove(groupId);
                  } else if (!expanded) {
                    _expandedCompletedGroups.add(groupId);
                  }
                }),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: MakoloSpacing.md,
                    vertical: MakoloSpacing.sm,
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.task_alt_rounded, size: 20),
                      const SizedBox(width: MakoloSpacing.sm),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              entries.length == 1
                                  ? 'Point terminé'
                                  : '${entries.length} Points terminés',
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                            Text(
                              last.timelineSummary?.isNotEmpty == true
                                  ? last.timelineSummary!
                                  : 'Résultat disponible dans l’historique',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodySmall
                                  ?.copyWith(color: muted),
                            ),
                          ],
                        ),
                      ),
                      Icon(
                        expanded
                            ? Icons.expand_less_rounded
                            : Icons.expand_more_rounded,
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (expanded)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  MakoloSpacing.sm,
                  0,
                  MakoloSpacing.sm,
                  MakoloSpacing.sm,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final entry in entries) ...[
                      if (entry.point.timelineSummary?.isNotEmpty == true)
                        Padding(
                          padding: const EdgeInsets.only(
                            left: MakoloSpacing.inner,
                            bottom: MakoloSpacing.xs,
                          ),
                          child: Text(
                            entry.point.timelineSummary!,
                            style: Theme.of(context).textTheme.labelSmall
                                ?.copyWith(color: muted),
                          ),
                        ),
                      _pointWidget(entry.point, readOnly: entry.readOnly),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _dayDivider(BuildContext context, DateTime date) {
    final local = date.toLocal();
    final now = DateTime.now();
    final title = DateUtils.isSameDay(local, now)
        ? "Aujourd'hui"
        : DateUtils.isSameDay(local, now.subtract(const Duration(days: 1)))
        ? 'Hier'
        : MaterialLocalizations.of(context).formatMediumDate(local);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.md),
      child: Center(
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Text(title, style: Theme.of(context).textTheme.labelSmall),
          ),
        ),
      ),
    );
  }

  Widget _pendingWidget(BuildContext context, ConversationOutgoing intent) {
    final blocked = intent.isBlocked;
    final state = intent.state;
    final (status, icon) = switch (state) {
      'confirmed' => ('Envoyé', Icons.check_rounded),
      'queued' => ('En attente', Icons.schedule_rounded),
      'in_flight' => ('Envoi en cours', Icons.schedule_rounded),
      'failed' => ('À réessayer', Icons.error_outline_rounded),
      'conflict' => ('Non envoyé · à vérifier', Icons.error_outline_rounded),
      _ => ('En attente de confirmation', Icons.help_outline_rounded),
    };
    final color = blocked
        ? Theme.of(context).colorScheme.error
        : Theme.of(context).colorScheme.onSurfaceVariant;
    return Padding(
      key: Key('conversation-outgoing-${intent.reference}'),
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.inner,
        0,
        MakoloSpacing.inner,
        MakoloSpacing.sm,
      ),
      child: ConversationPointShell(
        kind: intent.kind,
        isMine: true,
        publishedAt: intent.observedAt,
        statusIcon: Tooltip(
          message: status,
          child: Semantics(
            label: status,
            child: Icon(icon, size: 15, color: color),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (intent.title.trim().isNotEmpty)
              Text(
                intent.title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            if (intent.body.trim().isNotEmpty)
              Text(intent.body, style: Theme.of(context).textTheme.bodyMedium),
            if (intent.semanticMedia.isNotEmpty) ...[
              for (final media in intent.semanticMedia)
                if (media['scope'] == 'point')
                  _pendingSemanticMedia(context, media),
              if (intent.kind == 'poll')
                for (var index = 0; index < intent.options.length; index++)
                  Padding(
                    padding: const EdgeInsets.only(top: MakoloSpacing.sm),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(MakoloSpacing.sm),
                      decoration: BoxDecoration(
                        color: Theme.of(context)
                            .colorScheme
                            .surfaceContainerLow,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            intent.options[index],
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          for (final media in intent.semanticMedia)
                            if (media['scope'] == 'option' &&
                                media['option_index'] == index)
                              _pendingSemanticMedia(context, media),
                        ],
                      ),
                    ),
                  ),
            ],
            if (intent.mediaKind != null) ...[
              const SizedBox(height: MakoloSpacing.sm),
              if (intent.mediaKind == 'image' && intent.localFilePath != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.file(
                    File(intent.localFilePath!),
                    height: 155,
                    width: 250,
                    fit: BoxFit.cover,
                    cacheWidth: 750,
                    errorBuilder: (context, error, trace) => const Icon(
                      Icons.image_not_supported_outlined,
                      size: 48,
                    ),
                  ),
                )
              else
                Row(
                  children: [
                    Icon(
                      intent.mediaKind == 'voice' || intent.mediaKind == 'audio'
                          ? Icons.graphic_eq_rounded
                          : intent.mediaKind == 'video'
                          ? Icons.play_circle_outline_rounded
                          : Icons.insert_drive_file_outlined,
                      size: 22,
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: Text(
                        intent.filename ?? 'Pièce jointe',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _timeline(
    BuildContext context,
    _ConversationDetail detail, {
    List<ConversationOutgoing> outgoing = const [],
  }) {
    final entries = _timelineEntries(detail);
    final ownerReferences = <String>{
      for (final entry in entries)
        if (entry.point.clientReference != null) entry.point.clientReference!,
      for (final entry in entries) ...entry.point.exchangeReferences,
      // An owner-confirmed Point can fall outside the recent 40-item window
      // while still appearing in the legacy active/essential projections.
      for (final point in [
        ...detail.points,
        ...detail.essential,
        ...detail.elsewhere,
        if (detail.focusedPoint != null) detail.focusedPoint!,
      ])
        if (point.clientReference != null) point.clientReference!,
    };
    final visibleOutgoing = [
      for (final intent in outgoing)
        if (!(intent.isConfirmed && ownerReferences.contains(intent.reference)))
          intent,
    ];
    _positionTimeline(entries, visibleOutgoing);
    _focusAfterLayout();
    _activeTimelineSignature = _timelineSignature(detail);
    DateTime? previousDay;
    final children = <Widget>[];
    final olderCursor = _olderAvailableCursor(detail);
    final focusOutsideWindow =
        detail.hasTimeline &&
        detail.focusedPoint != null &&
        !entries.any((entry) => entry.point.id == detail.focusedPoint!.id);
    if (focusOutsideWindow) {
      children.add(
        Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: MakoloSpacing.inner,
            vertical: MakoloSpacing.sm,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                child: Text(
                  'Point ciblé · hors des derniers échanges',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ),
              _pointWidget(detail.focusedPoint!, readOnly: false),
            ],
          ),
        ),
      );
    }
    if (olderCursor != null && olderCursor.isNotEmpty) {
      children.add(
        Padding(
          padding: const EdgeInsets.fromLTRB(
            MakoloSpacing.inner,
            MakoloSpacing.sm,
            MakoloSpacing.inner,
            MakoloSpacing.md,
          ),
          child: Column(
            children: [
              OutlinedButton.icon(
                key: const Key('conversation-load-older'),
                onPressed: _loadingOlder
                    ? null
                    : () => _loadOlderPoints(detail),
                icon: _loadingOlder
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.keyboard_arrow_up_rounded),
                label: Text(
                  _loadingOlder
                      ? 'Chargement…'
                      : 'Voir les Points plus anciens',
                ),
              ),
              if (_olderError != null)
                Text(
                  _olderError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        ),
      );
    }
    // Owner points and Profile-private pending intents share one chronological
    // ordering. Pending files are not silently moved after newer publications.
    final combined =
        <
          ({
            DateTime? at,
            _ConversationTimelineEntry? point,
            ConversationOutgoing? outgoing,
            int order,
          })
        >[];
    var order = 0;
    for (final entry in entries) {
      combined.add((
        at: entry.point.publishedAt ?? entry.point.updatedAt,
        point: entry,
        outgoing: null,
        order: order++,
      ));
    }
    for (final intent in visibleOutgoing) {
      combined.add((
        at: intent.observedAt,
        point: null,
        outgoing: intent,
        order: order++,
      ));
    }
    combined.sort((left, right) {
      final a = left.at;
      final b = right.at;
      if (a != null && b != null) {
        final dateOrder = a.compareTo(b);
        if (dateOrder != 0) return dateOrder;
      } else if (a != null) {
        return 1;
      } else if (b != null) {
        return -1;
      }
      return left.order.compareTo(right.order);
    });
    var index = 0;
    while (index < combined.length) {
      final entry = combined[index];
      final local = entry.at?.toLocal();
      if (local != null &&
          (previousDay == null || !DateUtils.isSameDay(previousDay, local))) {
        children.add(_dayDivider(context, local));
        previousDay = local;
      }
      if (entry.point?.point.timelineCompact == true) {
        var next = index + 1;
        while (next < combined.length &&
            combined[next].point?.point.timelineCompact == true &&
            DateUtils.isSameDay(local, combined[next].at?.toLocal())) {
          next++;
        }
        children.add(
          _completedTimelineGroup(context, [
            for (final candidate in combined.sublist(index, next))
              candidate.point!,
          ]),
        );
        index = next;
      } else if (entry.point != null) {
        children.add(
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: _pointWidget(
              entry.point!.point,
              readOnly: entry.point!.readOnly,
            ),
          ),
        );
        index++;
      } else {
        children.add(_pendingWidget(context, entry.outgoing!));
        index++;
      }
    }
    if (children.isEmpty) {
      children.add(
        const Padding(
          padding: EdgeInsets.all(MakoloSpacing.inner),
          child: Center(child: Text('Aucun Point pour le moment.')),
        ),
      );
    }
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 860),
        // Keep focused Points mounted so ensureVisible can reach them even
        // when a deep link targets an older contribution.
        child: SingleChildScrollView(
          key: PageStorageKey<String>('conversation-detail-${widget.id}'),
          controller: _timelineScroll,
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          ),
        ),
      ),
    );
  }

  String _shortTitle(String title) {
    final separator = title.indexOf(' — ');
    return separator > 3 ? title.substring(0, separator).trim() : title;
  }

  void _openDetails() {
    final navigate = widget.onOpenDetails;
    if (navigate != null) {
      navigate();
      return;
    }
    // Widget test and embedded-route fallback: same real page, no short
    // informational modal and no duplicate business projection.
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (detailsContext) => ConversationDetailsScreen(
          repository: widget.repository,
          conversationId: widget.id,
          onOpenHistory: widget.onOpenHistory,
          onOpenConversation: () => Navigator.of(detailsContext).pop(),
        ),
      ),
    );
  }

  Widget _contextAvatar(_ConversationDetail detail) {
    final kind = detail.subject['kind']?.toString() ?? '';
    final uri = widget.repository.publicContextImageUri(
      detail.subject['image_url']?.toString(),
    );
    final colors = Theme.of(context).colorScheme;
    final fallback = CircleAvatar(
      radius: 18,
      backgroundColor: colors.primaryContainer,
      child: Icon(
        ConversationListTile.contextIcon(kind),
        size: 18,
        color: colors.onPrimaryContainer,
      ),
    );
    if (uri == null) return fallback;
    return ClipOval(
      child: Image.network(
        uri.toString(),
        width: 36,
        height: 36,
        fit: BoxFit.cover,
        excludeFromSemantics: true,
        errorBuilder: (_, _, _) => fallback,
      ),
    );
  }

  void _focusAfterLayout() {
    final id = _focusedPointId;
    if (id == null || id == _handledFocus) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || id != _focusedPointId) return;
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
            final available = projection != null;
            final freshness = available
                ? ConversationRepository.detailFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  )
                : null;
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
                  : source.lastErrorCode != null ||
                        (!available && _attemptedRefresh)
                  ? available
                        ? MakoloFailureCue.recoverable
                        : MakoloFailureCue.blocking
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            final permitted =
                surface.failure != MakoloFailureCue.permissionDenied &&
                surface.failure != MakoloFailureCue.blocking;
            final capabilities = detail.composer;
            final canCompose =
                capabilities['text_mode'] != null ||
                capabilities['can_create'] == true ||
                capabilities['can_form'] == true ||
                (capabilities['media_kinds'] is List &&
                    (capabilities['media_kinds'] as List).isNotEmpty);
            _activeComposer = capabilities;

            // The keyboard shrinks the body, not the conversation itself.
            // C3_bus will provide the compact composer visuals; C1_bus keeps
            // its existing widget reachable independently of timeline scroll.
            final usableHeight =
                MediaQuery.sizeOf(context).height -
                MediaQuery.viewInsetsOf(context).bottom;
            final composerLimit = (usableHeight * 0.38).clamp(116.0, 280.0);

            return Scaffold(
              resizeToAvoidBottomInset: true,
              appBar: AppBar(
                titleSpacing: 0,
                title: InkWell(
                  key: const Key('conversation-context-header'),
                  borderRadius: BorderRadius.circular(12),
                  onTap: available ? _openDetails : null,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        _contextAvatar(detail),
                        const SizedBox(width: MakoloSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                available
                                    ? _shortTitle(detail.title)
                                    : 'Conversation',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              if (available &&
                                  detail.contextLabel != null &&
                                  detail.contextLabel!.isNotEmpty)
                                Text(
                                  detail.contextLabel!,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                actions: [
                  if (widget.onOpenHistory != null)
                    MakoloIconActionButton(
                      key: const Key('conversation-open-history'),
                      tooltip: 'Rechercher · Historique',
                      onPressed: widget.onOpenHistory,
                      icon: Icons.manage_search_rounded,
                    ),
                  MakoloActionMenu(
                    tooltip: 'Options de la conversation',
                    onSelected: (selected) {
                      final action = selected.id;
                      if (action == 'refresh') {
                        unawaited(_refresh());
                      } else if (action == 'details') {
                        _openDetails();
                      } else {
                        unawaited(
                          _updatePersonalState(action, detail.personalState),
                        );
                      }
                    },
                    actions: [
                      const MakoloInteractionAction(
                        id: 'details',
                        label: 'Détails de la conversation',
                        intent: MakoloActionIntent.inspect,
                      ),
                      MakoloInteractionAction(
                        id: 'refresh',
                        label: 'Actualiser',
                        intent: MakoloActionIntent.transition,
                        enabled: !_refreshing,
                      ),
                      MakoloInteractionAction(
                        id: 'pin',
                        label: detail.personalState.pinned
                            ? 'Retirer l’épingle'
                            : 'Épingler pour moi',
                        intent: MakoloActionIntent.select,
                      ),
                      MakoloInteractionAction(
                        id: 'mute',
                        label: detail.personalState.muted
                            ? 'Réactiver les signaux'
                            : 'Mettre les signaux en sourdine',
                        intent: MakoloActionIntent.transition,
                      ),
                      MakoloInteractionAction(
                        id: 'revisit',
                        label: detail.personalState.revisit
                            ? 'Retirer le rappel de revisite'
                            : 'Revoir plus tard',
                        intent: MakoloActionIntent.transition,
                      ),
                      MakoloInteractionAction(
                        id: 'archive',
                        label: detail.personalState.archived
                            ? 'Retirer de mes archives'
                            : 'Archiver pour moi',
                        intent: MakoloActionIntent.transition,
                      ),
                      MakoloInteractionAction(
                        id: 'hide',
                        label: detail.personalState.hidden
                            ? 'Afficher de nouveau'
                            : 'Masquer pour moi',
                        intent: MakoloActionIntent.transition,
                      ),
                    ],
                  ),
                ],
              ),
              body: Column(
                children: [
                  if (available && permitted)
                    _attentionLens(
                      context,
                      _map(projection?.payload['attention']),
                    ),
                  if (available && permitted && _newMessagesAvailable)
                    Align(
                      alignment: Alignment.center,
                      child: TextButton.icon(
                        key: const Key('conversation-new-messages'),
                        onPressed: _showLatestMessages,
                        icon: const Icon(Icons.arrow_downward_rounded),
                        label: const Text('Nouveaux messages'),
                      ),
                    ),
                  Expanded(
                    child: available && permitted
                        ? StreamBuilder<List<ConversationOutgoing>>(
                            stream:
                                widget.repository.delivery?.watchOutgoing(
                                  widget.id,
                                ) ??
                                Stream.value(const <ConversationOutgoing>[]),
                            builder: (context, outgoingSnapshot) => _timeline(
                              context,
                              detail,
                              outgoing: outgoingSnapshot.data ?? const [],
                            ),
                          )
                        : MakoloSurfaceStateView(
                            state: surface,
                            initialLoading: const MakoloLoadingState(
                              label: 'Chargement de la conversation…',
                            ),
                            blockingErrorMessage: 'Cette conversation est indisponible ou n’a pas pu être chargée.',
                            onRetry: _refresh,
                            content: _timeline(context, detail),
                          ),
                  ),
                  if (available && permitted && canCompose)
                    SafeArea(
                      top: false,
                      child: ConstrainedBox(
                        constraints: BoxConstraints(maxHeight: composerLimit),
                        child: SingleChildScrollView(
                          child: ConversationComposer(
                            key: ValueKey<String>('composer-${widget.id}'),
                            repository: widget.repository,
                            conversationId: widget.id,
                            capabilities: capabilities,
                            representedSpaceId: widget.representedSpaceId,
                            onPublished: _afterPublish,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class _ConversationTimelineEntry {
  const _ConversationTimelineEntry({
    required this.point,
    required this.readOnly,
    required this.order,
  });

  final _ConversationPoint point;
  final bool readOnly;
  final int order;
}

class _PointCard extends StatefulWidget {
  const _PointCard({
    required this.point,
    required this.repository,
    required this.conversationId,
    this.representedSpaceId,
    this.readOnly = false,
    this.onOpenFormRequest,
    this.onOpenExchange,
    this.onRespondWithMedia,
    this.onOpenRelatedPoint,
  });

  final _ConversationPoint point;
  final ConversationRepository repository;
  final String conversationId;
  final String? representedSpaceId;
  final bool readOnly;
  final Future<void> Function(String requestId)? onOpenFormRequest;
  final VoidCallback? onOpenExchange;
  final ValueChanged<String>? onRespondWithMedia;
  final ValueChanged<String>? onOpenRelatedPoint;

  @override
  State<_PointCard> createState() => _PointCardState();
}

class _PointCardState extends State<_PointCard> {
  bool _busy = false;
  String? _feedback;
  String? _clientReference;
  Object? _lastValue;
  final Set<String> _choices = {};
  String _resolutionDraft = '';
  final Set<String> _resolutionSelections = {};

  @override
  void initState() {
    super.initState();
    _choices.addAll(
      widget.point.selectedOptionsForScope(widget.representedSpaceId),
    );
  }

  @override
  void didUpdateWidget(covariant _PointCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.point.id != widget.point.id ||
        oldWidget.representedSpaceId != widget.representedSpaceId ||
        oldWidget.point.responseForScope(
              oldWidget.representedSpaceId,
            )['submitted_at'] !=
            widget.point.responseForScope(
              widget.representedSpaceId,
            )['submitted_at']) {
      _choices
        ..clear()
        ..addAll(
          widget.point.selectedOptionsForScope(widget.representedSpaceId),
        );
    }
  }

  String _referenceFor(Object? value) {
    if (_lastValue.toString() != value.toString()) {
      _clientReference = null;
    }
    _lastValue = value;
    _clientReference ??=
        'mobile-${widget.point.id}-${DateTime.now().microsecondsSinceEpoch}';
    return _clientReference!;
  }

  Future<void> _toggleRevisit() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.repository.updatePointRevisit(
        conversationId: widget.conversationId,
        pointId: widget.point.id,
        revisit: !widget.point.revisit,
      );
      if (mounted)
        setState(
          () => _feedback = widget.point.revisit
              ? 'Repère personnel retiré.'
              : 'Point enregistré dans « À savoir ».',
        );
    } on Object {
      if (mounted)
        setState(
          () =>
              _feedback = 'Repère non confirmé. Réessayez après actualisation.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
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
      if (mounted) {
        setState(() => _feedback = 'Prise de connaissance enregistrée.');
      }
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
      if (mounted) setState(() => _feedback = 'Réponse enregistrée.');
    } on Object {
      try {
        await widget.repository.refreshDetail(widget.conversationId);
      } on Object {
        // The response remains unconfirmed until the owner can be reached.
      }
      if (mounted) {
        setState(
          () => _feedback = 'Envoi non confirmé. Vérifiez avant de réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _closeResponses() async {
    if (_busy) return;
    final approved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Clore les réponses ?'),
        content: const Text(
          'Les personnes ne pourront plus répondre à ce Point. '
          'Cette action ne modifie aucune autre donnée métier.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Clore'),
          ),
        ],
      ),
    );
    if (!mounted || approved != true) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.repository.closePointResponses(
        conversationId: widget.conversationId,
        pointId: widget.point.id,
      );
      if (mounted) setState(() => _feedback = 'Réponses closes.');
    } on Object {
      try {
        await widget.repository.refreshDetail(widget.conversationId);
      } on Object {
        // The authoritative state may have changed concurrently.
      }
      if (mounted) {
        setState(
          () => _feedback = 'Ce Point a pu changer. Clôture non confirmée : vérifiez son état.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resolvePoint() async {
    if (_busy) return;
    final controller = TextEditingController(text: _resolutionDraft);
    final selected = Set<String>.from(_resolutionSelections);
    try {
      final answer = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (dialogContext, refreshDialog) => AlertDialog(
            title: const Text('Résultat de coordination'),
            content: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Décrivez ce qui a été décidé. La résolution ne change '
                      'aucun statut de paiement, d’accès ou de démarche.',
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    TextField(
                      controller: controller,
                      maxLength: 500,
                      minLines: 2,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        labelText: 'Conclusion retenue',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (_) => refreshDialog(() {}),
                    ),
                    if (widget.point.kind == 'poll') ...[
                      const Text('Choix retenus (facultatif)'),
                      for (final option in widget.point.options)
                        CheckboxListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          title: Text(option.label),
                          value: selected.contains(option.id),
                          onChanged: (checked) => refreshDialog(() {
                            if (checked == true) {
                              selected.add(option.id);
                            } else {
                              selected.remove(option.id);
                            }
                          }),
                        ),
                    ],
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                child: const Text('Annuler'),
              ),
              FilledButton(
                onPressed: controller.text.trim().isEmpty
                    ? null
                    : () => Navigator.of(dialogContext).pop({
                        'summary': controller.text.trim(),
                        'options': selected.toList(),
                      }),
                child: const Text('Enregistrer le résultat'),
              ),
            ],
          ),
        ),
      );
      if (!mounted || answer == null) return;
      _resolutionDraft = answer['summary'] as String;
      _resolutionSelections
        ..clear()
        ..addAll((answer['options'] as List).cast<String>());
      setState(() {
        _busy = true;
        _feedback = null;
      });
      try {
        await widget.repository.resolvePoint(
          conversationId: widget.conversationId,
          pointId: widget.point.id,
          summary: _resolutionDraft,
          selectedOptionIds: _resolutionSelections.toList(),
        );
        _resolutionDraft = '';
        _resolutionSelections.clear();
        if (mounted) {
          setState(() => _feedback = 'Résultat de coordination enregistré.');
        }
      } on Object {
        try {
          await widget.repository.refreshDetail(widget.conversationId);
        } on Object {
          // Preserve the resolution draft for an explicit retry.
        }
        if (mounted) {
          setState(
            () => _feedback =
                'Résolution non confirmée. Votre texte est conservé ici.',
          );
        }
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    } finally {
      controller.dispose();
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
    final canRespond =
        (widget.representedSpaceId == null
            ? point.canRespond
            : point.responseWindowOpen) &&
        (!point.hasRespondedForScope(widget.representedSpaceId) ||
            point.canChangeResponse);
    final theme = Theme.of(context).textTheme;
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    final body = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (point.title.isNotEmpty)
          Text(
            point.title,
            style: point.kind == 'information'
                ? theme.bodyLarge
                : theme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
        if (point.body != null && point.body!.trim().isNotEmpty) ...[
          if (point.title.isNotEmpty) const SizedBox(height: MakoloSpacing.sm),
          Text(point.body!, style: theme.bodyMedium),
        ],
        if (point.deadlineAt != null && point.canRespond) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'Avant le ${MaterialLocalizations.of(context).formatShortDate(point.deadlineAt!)}',
            style: theme.bodySmall,
          ),
        ],
        // Point-level text and its own media stay together. Never append
        // choice/response media after all poll assertions.
        if (point.attachments.isNotEmpty)
          ConversationMediaGroup(
            key: Key('conversation-point-media-group-${point.id}'),
            repository: widget.repository,
            attachments: point.attachments,
          ),
        if (point.kind == 'poll' && point.options.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.md),
          Text(
            point.responseMode == 'multiple_choice'
                ? 'Choisissez une ou plusieurs réponses'
                : 'Choisissez une réponse',
            style: theme.titleSmall,
          ),
          for (final option in point.options)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.sm),
              child: Container(
                padding: const EdgeInsets.all(MakoloSpacing.sm),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        if (point.responseMode == 'multiple_choice' &&
                            canRespond &&
                            !widget.readOnly)
                          Checkbox(
                            value: _choices.contains(option.id),
                            onChanged: _busy
                                ? null
                                : (checked) => setState(() {
                                    if (checked == true) {
                                      _choices.add(option.id);
                                    } else {
                                      _choices.remove(option.id);
                                    }
                                  }),
                          )
                        else
                          Icon(
                            point
                                    .selectedOptionsForScope(
                                      widget.representedSpaceId,
                                    )
                                    .contains(option.id)
                                ? Icons.check_circle_rounded
                                : Icons.radio_button_unchecked_rounded,
                            size: 18,
                            color: muted,
                          ),
                        const SizedBox(width: MakoloSpacing.sm),
                        Expanded(
                          child: Text(option.label, style: theme.bodyMedium),
                        ),
                        if (point.responseMode == 'single_choice' &&
                            canRespond &&
                            !widget.readOnly)
                          TextButton(
                            onPressed: _busy
                                ? null
                                : () => _submitResponse(option.id),
                            child: const Text('Choisir'),
                          ),
                      ],
                    ),
                    if (option.attachments.isNotEmpty)
                      ConversationMediaGroup(
                        key: Key('conversation-option-media-${option.id}'),
                        repository: widget.repository,
                        attachments: option.attachments,
                      ),
                    if ((point.pollCountFor(option.id) ?? 0) > 0)
                      Padding(
                        padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                        child: Text(
                          '${point.pollCountFor(option.id)} sélection(s)',
                          style: theme.bodySmall?.copyWith(color: muted),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          if (point.pollResults['response_count'] is num &&
              (point.pollResults['response_count'] as num) > 0)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.sm),
              child: Text(
                '${point.pollResults['response_count']} participation(s) · '
                'résultats agrégés, sans identité des répondants',
                style: theme.bodySmall?.copyWith(color: muted),
              ),
            ),
          if (point.responseMode == 'multiple_choice' &&
              canRespond &&
              !widget.readOnly) ...[
            const SizedBox(height: MakoloSpacing.sm),
            MakoloActionButton(
              label: _busy ? 'Envoi…' : 'Valider mes choix',
              busy: _busy,
              appearance: MakoloActionAppearance.primary,
              onPressed: _busy || _choices.isEmpty
                  ? null
                  : () => _submitResponse(_choices.toList()..sort()),
            ),
          ],
        ],
        if (point.exchangePreview.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(MakoloSpacing.sm),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final entry in point.exchangePreview.take(2)) ...[
                  Text(
                    _string(entry['body']) ?? 'Contribution',
                    maxLines: 5,
                    overflow: TextOverflow.ellipsis,
                    style: theme.bodySmall,
                  ),
                  if (_maps(entry['attachments']).isNotEmpty)
                    ConversationMediaGroup(
                      repository: widget.repository,
                      attachments: _maps(entry['attachments']),
                    ),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
              ],
            ),
          ),
        ],
        if (point.formRequest != null && widget.onOpenFormRequest != null) ...[
          const SizedBox(height: MakoloSpacing.md),
          FilledButton.tonalIcon(
            onPressed: () => widget.onOpenFormRequest!(
              point.formRequest!['id']?.toString() ?? '',
            ),
            icon: const Icon(Icons.assignment_outlined),
            label: Text(
              point.formRequest!['status'] == 'completed'
                  ? 'Voir le formulaire'
                  : 'Compléter le formulaire',
            ),
          ),
        ],
        for (final response in point.responseMedia)
          if (_maps(response['attachments']).isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text('Réponse accessible', style: theme.labelSmall),
            if ((_string(response['label']) ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                child: Text(
                  _string(response['label'])!,
                  style: theme.bodyMedium,
                ),
              ),
            ConversationMediaGroup(
              repository: widget.repository,
              attachments: _maps(response['attachments']),
            ),
          ],
        if (point.kind == 'exchange' && widget.onOpenExchange != null)
          Align(
            alignment: Alignment.centerLeft,
            child: MakoloActionButton(
              key: Key('conversation-exchange-open-${point.id}'),
              label: 'Ouvrir la discussion',
              onPressed: widget.onOpenExchange,
              icon: Icons.forum_outlined,
              appearance: MakoloActionAppearance.quiet,
            ),
          ),
        if (point.hasRespondedForScope(widget.representedSpaceId))
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.check_circle_outline_rounded,
                  size: 15,
                  color: muted,
                ),
                const SizedBox(width: 5),
                Text(
                  point.responseLabelForScope(widget.representedSpaceId) ==
                              null ||
                          point
                              .responseLabelForScope(widget.representedSpaceId)!
                              .isEmpty
                      ? 'Réponse enregistrée'
                      : 'Réponse enregistrée : ${point.responseLabelForScope(widget.representedSpaceId)}',
                  style: theme.bodySmall?.copyWith(color: muted),
                ),
              ],
            ),
          ),
        if (point.responseCount != null && point.responseCount! > 0)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.xs),
            child: Text(
              point.responseCount == 1
                  ? '1 réponse'
                  : '${point.responseCount} réponses',
              style: theme.bodySmall?.copyWith(color: muted),
            ),
          ),
        if (point.replacedByPointId != null &&
            widget.onOpenRelatedPoint != null)
          Align(
            alignment: Alignment.centerLeft,
            child: MakoloActionButton(
              label: 'Voir le Point actuel',
              onPressed: () =>
                  widget.onOpenRelatedPoint!(point.replacedByPointId!),
              icon: Icons.call_made_rounded,
              appearance: MakoloActionAppearance.quiet,
            ),
          ),
        if (point.resolutionSummary != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text('✓ ${point.resolutionSummary!}'),
        ],
        if (_feedback != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text(_feedback!),
        ],
        if (!canRespond &&
            !point.hasRespondedForScope(widget.representedSpaceId) &&
            point.responseHint != null &&
            point.responseHint!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Text(
              point.responseHint!,
              style: theme.bodySmall?.copyWith(color: muted),
            ),
          ),
        if (!widget.readOnly) ...[
          Align(
            alignment: Alignment.centerRight,
            child: MakoloActionButton(
              key: Key('conversation-point-revisit-${point.id}'),
              label: _busy
                  ? 'Mise à jour…'
                  : point.revisit
                  ? 'Ne plus revoir ce Point'
                  : 'Revoir ce Point',
              icon: point.revisit
                  ? Icons.bookmark_added_rounded
                  : Icons.bookmark_add_outlined,
              onPressed: _busy ? null : _toggleRevisit,
              busy: _busy,
              appearance: MakoloActionAppearance.quiet,
            ),
          ),
        ],
        if (point.acknowledged)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Text(
              '✓ Prise de connaissance enregistrée',
              style: theme.bodySmall?.copyWith(color: muted),
            ),
          ),
        if (point.canAcknowledge && !widget.readOnly) ...[
          const SizedBox(height: MakoloSpacing.md),
          MakoloActionButton(
            label: _busy ? 'En cours…' : 'J’ai pris connaissance',
            onPressed: _busy ? null : _acknowledge,
            busy: _busy,
            appearance: MakoloActionAppearance.primary,
          ),
        ],
        if (canRespond &&
            (point.responseMode == 'file' || point.responseMode == 'voice') &&
            !widget.readOnly &&
            widget.onRespondWithMedia != null) ...[
          const SizedBox(height: MakoloSpacing.sm),
          if (point.responseMode == 'voice')
            FilledButton.tonalIcon(
              key: Key('conversation-point-media-${point.id}'),
              onPressed: () => widget.onRespondWithMedia!('voice'),
              icon: const Icon(Icons.mic_none_rounded),
              label: const Text('Répondre par vocal'),
            )
          else
            Wrap(
              spacing: MakoloSpacing.sm,
              children: [
                FilledButton.tonalIcon(
                  key: Key('conversation-point-media-${point.id}'),
                  onPressed: () => widget.onRespondWithMedia!('document'),
                  icon: const Icon(Icons.attach_file_rounded),
                  label: const Text('Joindre un fichier'),
                ),
                MakoloActionButton(
                  label: 'Photo',
                  appearance: MakoloActionAppearance.quiet,
                  onPressed: () => widget.onRespondWithMedia!('photo'),
                  icon: Icons.image_outlined,
                ),
              ],
            ),
        ],
        if (canRespond &&
            point.responseMode != 'file' &&
            point.responseMode != 'voice' &&
            point.kind != 'exchange' &&
            point.kind != 'poll' &&
            !widget.readOnly) ...[
          const SizedBox(height: MakoloSpacing.md),
          if (point.responseMode == 'boolean')
            Wrap(
              spacing: MakoloSpacing.sm,
              children: [
                MakoloActionButton(
                  label: point.kind == 'request'
                      ? "Je m'en charge"
                      : 'Oui, je confirme',
                  onPressed: _busy ? null : () => _submitResponse(true),
                ),
                MakoloActionButton(
                  label: point.kind == 'request'
                      ? 'Je ne peux pas'
                      : 'Non, je ne confirme pas',
                  onPressed: _busy ? null : () => _submitResponse(false),
                ),
              ],
            )
          else if (point.responseMode == 'single_choice')
            Wrap(
              spacing: MakoloSpacing.sm,
              runSpacing: MakoloSpacing.sm,
              children: [
                for (final option in point.options)
                  MakoloActionButton(
                    label: option.label,
                    onPressed: _busy ? null : () => _submitResponse(option.id),
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
                MakoloActionButton(
                  label: _busy ? 'Envoi…' : 'Répondre',
                  busy: _busy,
                  appearance: MakoloActionAppearance.primary,
                  onPressed: _busy || _choices.isEmpty
                      ? null
                      : () => _submitResponse(_choices.toList()),
                ),
              ],
            )
          else if (point.supportsInteractiveResponse)
            MakoloActionButton(
              label: _busy ? 'Envoi…' : point.responseActionLabel,
              busy: _busy,
              appearance: MakoloActionAppearance.primary,
              onPressed: _busy ? null : _respond,
            ),
        ],
        if ((point.canCloseResponses || point.canResolve) && !widget.readOnly)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: ExpansionTile(
              key: Key('conversation-point-management-${point.id}'),
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
              title: const Text('Gérer ce Point'),
              leading: const Icon(Icons.tune_rounded, size: 20),
              dense: true,
              initiallyExpanded: false,
              children: [
                Text(
                  'Clore les réponses ou consigner un résultat de coordination. '
                  'Cela ne modifie pas les données métier du contexte.',
                  style: theme.bodySmall?.copyWith(color: muted),
                ),
                const SizedBox(height: MakoloSpacing.sm),
                Wrap(
                  spacing: MakoloSpacing.sm,
                  runSpacing: MakoloSpacing.sm,
                  children: [
                    if (point.canCloseResponses)
                      OutlinedButton.icon(
                        onPressed: _busy ? null : _closeResponses,
                        icon: const Icon(Icons.lock_clock_outlined),
                        label: const Text('Clore les réponses'),
                      ),
                    if (point.canResolve)
                      FilledButton.tonalIcon(
                        onPressed: _busy ? null : _resolvePoint,
                        icon: const Icon(Icons.fact_check_outlined),
                        label: const Text('Consigner le résultat'),
                      ),
                  ],
                ),
              ],
            ),
          ),
      ],
    );
    return ConversationPointShell(
      key: Key('conversation-point-shell-${point.id}'),
      kind: point.kind ?? 'information',
      isMine: point.isMine,
      authorLabel: point.authorLabel,
      representedSpace: point.representedSpace,
      representedSpaceLabel: point.representedSpaceLabel,
      publishedAt: point.publishedAt ?? point.updatedAt,
      // Owner-confirmed publication is known. Delivery/read receipts need
      // separate authenticated evidence and are never inferred here.
      statusIcon: point.isMine && point.publishedAt != null
          ? const Tooltip(
              message: 'Envoyé',
              child: Icon(Icons.check_rounded, size: 15),
            )
          : null,
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
                  MakoloActionButton(
                    label: 'Annuler',
                    appearance: MakoloActionAppearance.quiet,
                    onPressed: () => Navigator.pop(context, _cancelledResponse),
                  ),
                  MakoloActionButton(
                    label: 'Continuer',
                    appearance: MakoloActionAppearance.primary,
                    onPressed: selected.isEmpty
                        ? null
                        : () => Navigator.pop(
                            context,
                            selected.toList(growable: false),
                          ),
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
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(context, _cancelledResponse),
            ),
            MakoloActionButton(
              label: 'Envoyer',
              appearance: MakoloActionAppearance.primary,
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) Navigator.pop(context, value);
              },
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
    this.unreadCount = 0,
    required this.allClear,
    this.contextLabel,
    this.purpose,
    this.latestResult,
    this.updatedAt,
    this.matchedPointId,
    this.subtitle,
    this.preview,
    this.previewKind,
    this.contextKind = '',
    this.contextImageUrl,
    this.mediaKinds = const [],
  });

  final String id;
  final String title;
  final String? lifecycle;
  final int attentionCount;
  final int unreadCount;
  final bool allClear;
  final String? contextLabel;
  final String? purpose;
  final String? latestResult;
  final DateTime? updatedAt;
  final String? matchedPointId;
  final String? subtitle;
  final String? preview;
  final String? previewKind;
  final String contextKind;
  final String? contextImageUrl;
  final List<String> mediaKinds;

  static String _fallbackTitle(String original, String? context, String kind) {
    if (kind == 'direct') return context ?? original;
    if (context == null || !original.contains(context)) return original;
    for (final separator in [' — ', ' – ']) {
      if (context.contains(separator)) {
        return context.split(separator).first.trim();
      }
    }
    return context;
  }

  static String? _fallbackContext(String? context, String kind) {
    if (kind == 'direct') return 'Conversation directe';
    if (context != null) {
      for (final separator in [' — ', ' – ']) {
        final index = context.indexOf(separator);
        if (index >= 0 && index + separator.length < context.length) {
          return context.substring(index + separator.length).trim();
        }
      }
    }
    return switch (kind) {
      'space' => 'Espace',
      'group' => 'Groupe',
      'activity' => 'Activité',
      'occurrence' => 'Occurrence',
      'journey' => 'Démarche',
      'dossier' => 'Dossier',
      'project' => 'Projet',
      'action_proposal' => 'Proposition',
      _ => null,
    };
  }

  factory _ConversationSummary.fromMap(Map<String, dynamic> row) {
    final context = _map(row['context']);
    final card = _map(row['card']);
    final contextKind =
        _string(card['context_kind']) ?? _string(context['kind']) ?? '';
    final original = _string(row['title']) ?? 'Conversation';
    final contextLabel = _string(context['label']);
    final title =
        _string(card['title']) ??
        _fallbackTitle(original, contextLabel, contextKind);
    final last = _map(row['last_message']);
    final preview =
        (last['removed'] == true
            ? 'Message supprimé'
            : _string(last['body'])) ??
        _string(card['preview']) ??
        _string(row['latest_result']) ??
        _string(row['purpose']);
    return _ConversationSummary(
      id: _string(row['id']) ?? '',
      title: title,
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
      unreadCount: row['unread_count'] is int ? row['unread_count'] as int : 0,
      updatedAt: DateTime.tryParse(
        _string(last['created_at']) ?? _string(row['updated_at']) ?? '',
      ),
      matchedPointId: _string(row['matched_point_id']),
      subtitle:
          _string(card['context_label']) ??
          _fallbackContext(contextLabel, contextKind),
      preview: preview == title ? null : preview,
      previewKind:
          _string(card['preview_kind']) ??
          (row['latest_result'] != null ? 'result' : 'purpose'),
      contextKind: contextKind,
      contextImageUrl: _string(card['context_image_url']),
      mediaKinds: row['card'] is Map && card['media_kinds'] is List
          ? (card['media_kinds'] as List).whereType<String>().toList(
              growable: false,
            )
          : const [],
    );
  }

  static List<_ConversationSummary> fromProjection(
    StoredProjection? projection,
  ) =>
      _maps(projection?.payload['results'])
          .map(_ConversationSummary.fromMap)
          .where((item) => item.id.isNotEmpty)
          .toList(growable: false);
}

class _ConversationDetail {
  const _ConversationDetail({
    required this.title,
    required this.points,
    required this.essential,
    this.timeline = const [],
    this.timelineNextCursor,
    this.hasTimeline = false,
    required this.personalState,
    this.composer = const {},
    this.elsewhere = const [],
    this.focusedPoint,
    this.purpose,
    this.lifecycle,
    this.contextLabel,
    this.subject = const {},
  });

  final Map<String, dynamic> subject;
  final String title;
  final String? purpose;
  final String? lifecycle;
  final String? contextLabel;
  final List<_ConversationPoint> points;
  final List<_ConversationPoint> essential;
  final List<_ConversationPoint> timeline;
  final String? timelineNextCursor;
  final bool hasTimeline;
  final List<_ConversationPoint> elsewhere;
  final _ConversationPoint? focusedPoint;
  final _ConversationPersonalState personalState;
  final Map<String, dynamic> composer;

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
      subject: _map(payload['subject']).isNotEmpty
          ? _map(payload['subject'])
          : context,
      points: _maps(payload['points'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      timeline: _maps(payload['timeline'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      hasTimeline: payload['timeline'] is List,
      timelineNextCursor: _string(payload['timeline_next_cursor']),
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
      composer: _map(payload['composer']),
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

Widget _pendingSemanticMedia(BuildContext context, Map<String, dynamic> media) {
  final path = media['path']?.toString() ?? '';
  final filename = media['filename']?.toString() ?? 'Média';
  final kind = media['kind']?.toString();
  final caption = media['caption']?.toString() ?? '';
  return Padding(
    padding: const EdgeInsets.only(top: MakoloSpacing.sm),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (kind == 'image' && path.isNotEmpty)
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.file(
              File(path),
              height: 150,
              width: 250,
              fit: BoxFit.contain,
              cacheWidth: 750,
              errorBuilder: (context, error, trace) =>
                  const Icon(Icons.image_not_supported_outlined),
            ),
          )
        else
          Row(
            children: [
              Icon(
                kind == 'voice' || kind == 'audio'
                    ? Icons.graphic_eq_rounded
                    : kind == 'video'
                    ? Icons.play_circle_outline_rounded
                    : Icons.description_outlined,
              ),
              const SizedBox(width: MakoloSpacing.sm),
              Expanded(
                child: Text(
                  filename,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ],
          ),
        if (caption.trim().isNotEmpty)
          Text(caption, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );
}

class _ConversationOption {
  const _ConversationOption({
    required this.id,
    required this.label,
    this.attachments = const [],
  });

  final String id;
  final String label;
  final List<Map<String, dynamic>> attachments;

  factory _ConversationOption.fromMap(Map<String, dynamic> row) =>
      _ConversationOption(
        id: _string(row['id']) ?? '',
        label: _string(row['label']) ?? '',
        attachments: _maps(row['attachments']),
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
    this.exchangePreview = const [],
    this.attachments = const [],
    this.responseMedia = const [],
    this.formRequest,
    this.responseStatus = const {},
    this.timelineCompact = false,
    this.timelineSummary,
    this.myResponse = const {},
    this.pollResults = const {},
    this.representedResponses = const [],
    this.responseWindowOpen = false,
    this.responseHint,
    this.canAcknowledge = false,
    this.acknowledged = false,
    this.revisit = false,
    this.canCloseResponses = false,
    this.canResolve = false,
    this.canChangeResponse = false,
    this.replacedByPointId,
    this.authorLabel,
    this.isMine = false,
    this.representedSpace = false,
    this.representedSpaceLabel,
    this.clientReference,
    this.exchangeReferences = const [],
  });

  final String id;
  final String title;
  final String? authorLabel;
  final bool isMine;
  final bool representedSpace;
  final String? representedSpaceLabel;
  final String? clientReference;
  final List<String> exchangeReferences;
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
  final List<Map<String, dynamic>> exchangePreview;
  final List<Map<String, dynamic>> attachments;
  final List<Map<String, dynamic>> responseMedia;
  final Map<String, dynamic>? formRequest;
  final Map<String, dynamic> responseStatus;
  final bool timelineCompact;
  final String? timelineSummary;
  final Map<String, dynamic> myResponse;
  final Map<String, dynamic> pollResults;
  final List<Map<String, dynamic>> representedResponses;
  final bool responseWindowOpen;
  final String? responseHint;
  final bool canAcknowledge;
  final bool acknowledged;
  final bool revisit;
  final bool canCloseResponses;
  final bool canResolve;
  final bool canChangeResponse;
  final String? replacedByPointId;

  bool get hasResponded => responseStatus['responded'] == true;
  int? get responseCount => responseStatus['response_count'] is num
      ? (responseStatus['response_count'] as num).toInt()
      : null;

  Map<String, dynamic> responseForScope(String? spaceId) {
    if (spaceId == null || spaceId.isEmpty) return myResponse;
    for (final response in representedResponses) {
      if (_string(response['space_id']) == spaceId) return response;
    }
    return const {};
  }

  bool hasRespondedForScope(String? spaceId) =>
      responseForScope(spaceId).containsKey('submitted_at');

  Set<String> selectedOptionsForScope(String? spaceId) {
    final value = responseForScope(spaceId)['value'];
    if (value is List) return value.map((item) => item.toString()).toSet();
    return value == null ? <String>{} : {value.toString()};
  }

  Set<String> get mySelectedOptions => selectedOptionsForScope(null);

  int? pollCountFor(String optionId) {
    final count = _map(pollResults['counts'])[optionId];
    return count is num ? count.toInt() : null;
  }

  String? responseLabelForScope(String? spaceId) {
    final response = responseForScope(spaceId);
    if (!response.containsKey('value')) return null;
    final value = response['value'];
    if (responseMode == 'single_choice' || responseMode == 'multiple_choice') {
      final selected = selectedOptionsForScope(spaceId);
      return options
          .where((option) => selected.contains(option.id))
          .map((option) => option.label)
          .join(', ');
    }
    if (value is bool) {
      if (kind == 'request') {
        return value ? 'Je m’en charge' : 'Je ne peux pas';
      }
      return value ? 'Oui' : 'Non';
    }
    return value?.toString();
  }

  String? get myResponseLabel => responseLabelForScope(null);

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
    'boolean' when kind == 'request' => "Prendre en charge",
    'boolean' => 'Confirmer',
    'single_choice' || 'multiple_choice' => 'Choisir',
    'date' || 'datetime' => 'Indiquer',
    _ => 'Répondre',
  };

  factory _ConversationPoint.fromMap(Map<String, dynamic> row) {
    return _ConversationPoint(
      id: _string(row['id']) ?? '',
      title: _string(row['title']) ?? '',
      authorLabel: _string(_map(row['author'])['label']),
      isMine: _map(row['author'])['is_mine'] == true,
      representedSpace: _map(row['author'])['represented_space'] == true,
      representedSpaceLabel: _string(_map(row['author'])['space_label']),
      clientReference: _string(row['client_reference']),
      exchangeReferences: [
        for (final entry in _maps(row['exchange_preview']))
          if (_string(entry['client_reference']) != null)
            _string(entry['client_reference'])!,
      ],
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
      attachments: _maps(row['attachments']),
      responseMedia: _maps(row['response_media']),
      formRequest: _map(row['form_request']).isEmpty
          ? null
          : _map(row['form_request']),
      responseStatus: _map(row['response_status']),
      timelineCompact: row['timeline_compact'] == true,
      timelineSummary: _string(row['timeline_summary']),
      myResponse: _map(row['my_response']),
      pollResults: _map(row['poll_results']),
      representedResponses: _maps(row['represented_responses']),
      responseWindowOpen: row['response_window_open'] == true,
      responseHint: _string(row['response_hint']),
      canAcknowledge: row['can_acknowledge'] == true,
      acknowledged: row['acknowledged'] == true,
      revisit: row['revisit'] == true,
      canCloseResponses: row['can_close_responses'] == true,
      canResolve: row['can_resolve'] == true,
      canChangeResponse: row['can_change_response'] == true,
      replacedByPointId: _string(row['replaced_by_point_id']),
      exchangePreview: _maps(row['exchange_preview']),
    );
  }
}

class _ConversationInvitation {
  const _ConversationInvitation({
    required this.id,
    required this.conversationId,
    required this.status,
    this.collective = false,
    this.label,
    this.identifier,
    this.invitedBy,
    this.canAccept = true,
    this.expiresAt,
    this.createdAt,
  });

  final String id;
  final String conversationId;
  final String status;
  final bool collective;
  final String? label;
  final String? identifier;
  final String? invitedBy;
  final bool canAccept;
  final DateTime? expiresAt;
  final DateTime? createdAt;

  bool get expired {
    final value = expiresAt;
    return status == 'expired' ||
        (value != null && !DateTime.now().isBefore(value));
  }

  static List<_ConversationInvitation> fromProjection(
    StoredProjection? projection,
  ) {
    final results = <_ConversationInvitation>[];
    for (final row in _maps(projection?.payload['results'])) {
      if (row['status'] != 'pending') continue;
      final id = _string(row['id']);
      if (id == null || id.isEmpty) continue;
      results.add(
        _ConversationInvitation(
          id: id,
          conversationId: _string(row['conversation_id']) ?? '',
          status: _string(row['status']) ?? '',
          invitedBy: _string(row['invited_by']),
          canAccept: row['can_accept'] != false,
          expiresAt: DateTime.tryParse(_string(row['expires_at']) ?? ''),
          createdAt: DateTime.tryParse(_string(row['created_at']) ?? ''),
        ),
      );
    }
    for (final row in _maps(projection?.payload['collective_results'])) {
      if (row['status'] != 'pending') continue;
      final id = _string(row['id']);
      if (id == null || id.isEmpty) continue;
      results.add(
        _ConversationInvitation(
          id: id,
          conversationId: _string(row['conversation_id']) ?? '',
          status: _string(row['status']) ?? '',
          collective: true,
          label: _string(row['label']),
          identifier: _string(row['identifier']),
          invitedBy: _string(row['invited_by']),
          canAccept: row['can_accept'] != false,
          expiresAt: DateTime.tryParse(_string(row['expires_at']) ?? ''),
          createdAt: DateTime.tryParse(_string(row['created_at']) ?? ''),
        ),
      );
    }
    results.sort(
      (a, b) => (a.createdAt ?? DateTime(2000)).compareTo(
        b.createdAt ?? DateTime(2000),
      ),
    );
    return results;
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
