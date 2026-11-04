import 'dart:async';

import 'package:flutter/material.dart';

import '../app/runtime/app_runtime.dart';
import '../data/local/profile_store.dart';
import '../design/behavior_states.dart';
import '../design/makolo_theme.dart';
import '../design/surface_states.dart';
import '../features/settings/notification_preferences_screen.dart' as settings;
import '../presentation/projection_surface_adapter.dart';
import '../selectors/projection_selector.dart';
import '../sync/freshness.dart';
import '../sync/owner_source_state.dart';
import 'notification_repository.dart';
import 'notification_router.dart';

class NotificationInboxScreen extends StatefulWidget {
  const NotificationInboxScreen({
    super.key,
    required this.repository,
    required this.onOpenDestination,
    this.runtime,
  });

  final NotificationRepository repository;
  final AppRuntime? runtime;
  final Future<void> Function(String path) onOpenDestination;

  @override
  State<NotificationInboxScreen> createState() =>
      _NotificationInboxScreenState();
}

class _NotificationInboxScreenState extends State<NotificationInboxScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  final ScrollController _scroll = ScrollController();
  bool _refreshing = false;
  bool _attempted = false;
  bool _loadFailed = false;
  bool _loadingMore = false;
  bool _pageFailed = false;
  bool _onlyUnread = false;
  bool _requestedUnread = false;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_maybeLoadMore);
    unawaited(_acquire());
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _acquire() async {
    try {
      final local = await widget.repository.readList(onlyUnread: _onlyUnread);
      final source = await widget.repository.readListSource(onlyUnread: _onlyUnread);
      if (!mounted) return;
      if (local == null ||
          NotificationRepository.listFreshness.evaluate(
                local,
                now: DateTime.now(),
                invalidated: source.invalidated,
              ) != FreshnessState.fresh) {
        await _refresh();
      } else {
        setState(() => _attempted = true);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _attempted = true;
          _loadFailed = true;
        });
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    _requestedUnread = _onlyUnread;
    setState(() {
      _refreshing = true;
      _pageFailed = false;
      _loadFailed = false;
    });
    try {
      await widget.repository.refreshList(onlyUnread: _requestedUnread);
    } on Object {
      if (mounted) setState(() => _loadFailed = true);
    } finally {
      if (mounted) {
        setState(() {
          _attempted = true;
          _refreshing = false;
        });
        if (_requestedUnread != _onlyUnread) unawaited(_acquire());
      }
    }
  }

  void _maybeLoadMore() {
    if (!mounted || _refreshing || _loadingMore || _pageFailed) return;
    if (!_scroll.hasClients || _scroll.position.extentAfter > 500) return;
    unawaited(_loadMore());
  }

  Future<void> _loadMore() async {
    if (_loadingMore || _refreshing) return;
    final snapshot = await widget.repository.readList(onlyUnread: _onlyUnread);
    if (!mounted || snapshot?.payload['next'] is! String) return;
    if (_onlyUnread && snapshot?.payload['unread_count'] == 0) return;
    setState(() {
      _loadingMore = true;
      _pageFailed = false;
    });
    try {
      await widget.repository.loadMore(onlyUnread: _onlyUnread);
    } on Object {
      if (mounted) setState(() => _pageFailed = true);
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _chooseFilter(bool unreadOnly) {
    if (_onlyUnread == unreadOnly) return;
    setState(() {
      _onlyUnread = unreadOnly;
      _pageFailed = false;
      _loadFailed = false;
      _attempted = false;
    });
    unawaited(_acquire());
  }

  Future<void> _markAllRead() async {
    try {
      await widget.repository.markAllRead();
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Lecture non confirmée. Réessayez.')),
      );
    }
  }

  Future<void> _confirmRead(String id) async {
    try {
      await widget.repository.markRead(id);
    } on Object {
      // Keep the existing unread state if the server cannot confirm reading.
    }
  }

  Future<void> _open(_NotificationRow row) async {
    // Reading must never delay opening the destination on a slow connection.
    if (!row.isRead) unawaited(_confirmRead(row.id));
    final path = row.destinationPath;
    if (!mounted || path == null) return;
    await widget.onOpenDestination(path);
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      key: ValueKey<bool>(_onlyUnread),
      stream: widget.repository.watchList(onlyUnread: _onlyUnread),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          key: ValueKey<String>('source-$_onlyUnread'),
          stream: widget.repository.watchListSource(onlyUnread: _onlyUnread),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final rows = _NotificationRow.fromProjection(projection);
            final visible = _onlyUnread
                ? rows.where((row) => !row.isRead).toList(growable: false)
                : rows;
            final freshness = projection == null
                ? null
                : NotificationRepository.listFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = projection != null;
            final hasMore = projection?.payload['next'] is String;
            final pendingUnread = projection?.payload['unread_count'];
            final noneUnread = _onlyUnread && pendingUnread is num && pendingUnread == 0;
            final state = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? (visible.isEmpty && (!hasMore || noneUnread))
                        ? MakoloAvailabilityCue.empty
                        : MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: available
                  ? (source.lastErrorCode != null || _loadFailed)
                        ? MakoloFailureCue.recoverable
                        : MakoloFailureCue.none
                  : (_attempted && !_refreshing)
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            final total = projection?.payload['total_count'];
            final unread = projection?.payload['unread_count'];
            final filteredCount = projection?.payload['count'];
            final remaining = filteredCount is num &&
                    filteredCount.toInt() > rows.length
                ? filteredCount.toInt() - rows.length
                : 0;
            WidgetsBinding.instance.addPostFrameCallback((_) => _maybeLoadMore());

            return Scaffold(
              appBar: AppBar(
                title: const Text('Notifications'),
                actions: [
                  IconButton(
                    tooltip: 'Préférences',
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => settings.NotificationPreferencesScreen(
                          repository: widget.repository,
                          runtime: widget.runtime,
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.tune_rounded),
                  ),
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloSurfaceStateView(
                state: state,
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement des notifications…',
                ),
                recoverableErrorMessage: 'Actualisation indisponible.',
                empty: MakoloEmptyState(
                  title: _onlyUnread
                      ? 'Aucune notification non lue.'
                      : 'Aucune notification.',
                ),
                onRetry: _refresh,
                content: Column(
                  children: [
                    if (total is num && unread is num)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(
                          MakoloSpacing.inner,
                          MakoloSpacing.sm,
                          MakoloSpacing.inner,
                          0,
                        ),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Wrap(
                            spacing: MakoloSpacing.md,
                            runSpacing: 4,
                            children: [
                              Text('${total.toInt()} notifications'),
                              Text(
                                '${unread.toInt()} non lues',
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(
                        MakoloSpacing.inner,
                        MakoloSpacing.sm,
                        MakoloSpacing.inner,
                        MakoloSpacing.sm,
                      ),
                      child: Wrap(
                        spacing: MakoloSpacing.sm,
                        runSpacing: MakoloSpacing.sm,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          ChoiceChip(
                            label: const Text('Toutes'),
                            selected: !_onlyUnread,
                            onSelected: (_) => _chooseFilter(false),
                          ),
                          ChoiceChip(
                            label: const Text('Non lues'),
                            selected: _onlyUnread,
                            onSelected: (_) => _chooseFilter(true),
                          ),
                          if (unread is num && unread > 0)
                            TextButton(
                              onPressed: _markAllRead,
                              child: const Text('Tout marquer comme lu'),
                            ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: RefreshIndicator(
                        onRefresh: _refresh,
                        child: ListView.builder(
                          controller: _scroll,
                          key: const PageStorageKey<String>('notification-inbox-list'),
                          physics: const AlwaysScrollableScrollPhysics(),
                          itemCount: visible.length + 1,
                          itemBuilder: (context, index) {
                            if (index == visible.length) {
                              if (_pageFailed) {
                                return Center(
                                  child: TextButton(
                                    onPressed: () {
                                      setState(() => _pageFailed = false);
                                      unawaited(_loadMore());
                                    },
                                    child: const Text('Réessayer'),
                                  ),
                                );
                              }
                              if (_loadingMore) {
                                return const Padding(
                                  padding: EdgeInsets.all(16),
                                  child: Center(child: CircularProgressIndicator()),
                                );
                              }
                              return Padding(
                                padding: const EdgeInsets.all(20),
                                child: Center(
                                  child: Text(
                                    hasMore
                                        ? '${remaining} autres à afficher'
                                        : 'Vous avez tout vu',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ),
                              );
                            }
                            final row = visible[index];
                            return Column(
                              children: [
                                Semantics(
                                  button: true,
                                  label: '${row.isRead ? 'Lue. ' : 'Non lue. '}${row.title}. ${row.message}',
                                  child: InkWell(
                                    onTap: () => _open(row),
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: MakoloSpacing.inner,
                                        vertical: MakoloSpacing.md,
                                      ),
                                      child: Row(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          SizedBox(
                                            width: 16,
                                            child: Padding(
                                              padding: const EdgeInsets.only(top: 8),
                                              child: row.isRead
                                                  ? const SizedBox.shrink()
                                                  : Icon(
                                                      Icons.circle,
                                                      size: 8,
                                                      color: Theme.of(context).colorScheme.primary,
                                                    ),
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text(
                                                  row.title,
                                                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                                    fontWeight: row.isRead
                                                        ? FontWeight.w500
                                                        : FontWeight.w700,
                                                  ),
                                                ),
                                                if (row.message.isNotEmpty) ...[
                                                  const SizedBox(height: 4),
                                                  Text(
                                                    row.message,
                                                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                                                    ),
                                                  ),
                                                ],
                                                if (row.createdAt != null) ...[
                                                  const SizedBox(height: 6),
                                                  Text(
                                                    _timeLabel(row.createdAt!),
                                                    style: Theme.of(context).textTheme.bodySmall,
                                                  ),
                                                ],
                                              ],
                                            ),
                                          ),
                                          if (row.destinationPath != null) ...[
                                            const SizedBox(width: 8),
                                            const Icon(Icons.chevron_right_rounded),
                                          ],
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                                const Divider(height: 1),
                              ],
                            );
                          },
                        ),
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

class _NotificationRow {
  const _NotificationRow({
    required this.id,
    required this.title,
    required this.message,
    required this.isRead,
    this.createdAt,
    this.destinationPath,
  });

  final String id;
  final String title;
  final String message;
  final bool isRead;
  final DateTime? createdAt;
  final String? destinationPath;

  static List<_NotificationRow> fromProjection(StoredProjection? projection) {
    final raw = projection?.payload['results'];
    if (raw is! List) return const [];
    const router = NotificationRouter();
    return raw
        .whereType<Map>()
        .map((item) {
          final row = item.map((key, value) => MapEntry(key.toString(), value));
          final path = router.resolveNavigation(row['navigation']);
          final rawTitle = row['title']?.toString().trim() ?? '';
          final rawMessage = row['message']?.toString().trim() ?? '';
          // Legacy owner messages already contain a useful specific subject.
          final confirmed = rawTitle == 'Confirmation Makolo'
              ? RegExp(r'^Votre démarche pour «(.+)» est confirmée[.!]?
            createdAt: DateTime.tryParse(row['created_at']?.toString() ?? ''),
            destinationPath: path,
          );
        })
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }
}

String _timeLabel(DateTime value) {
  final date = value.toLocal();
  final now = DateTime.now();
  final elapsed = now.difference(date);
  if (elapsed.isNegative || elapsed.inMinutes < 1) return 'À l’instant';
  if (elapsed.inMinutes < 60) return 'Il y a ${elapsed.inMinutes} min';
  if (elapsed.inHours < 24 && date.day == now.day) {
    return 'Il y a ${elapsed.inHours} h';
  }
  final day = DateTime(date.year, date.month, date.day);
  final today = DateTime(now.year, now.month, now.day);
  final days = today.difference(day).inDays;
  if (days == 1) return 'Hier';
  if (days < 7) return 'Il y a ${days} jours';
  if (days < 30) return 'Il y a ${(days / 7).floor()} semaines';
  if (days < 365) return 'Il y a ${(days / 30).floor()} mois';
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
}
)
                  .firstMatch(rawMessage)
              : null;
          return _NotificationRow(
            id: row['id']?.toString() ?? '',
            title: confirmed?.group(1) ??
                (rawTitle == 'Confirmation Makolo'
                    ? 'Démarche confirmée'
                    : rawTitle.isEmpty
                        ? 'Notification'
                        : rawTitle),
            message: confirmed == null
                ? rawMessage
                : 'Votre démarche est confirmée.',
            isRead: row['is_read'] == true,
            createdAt: DateTime.tryParse(row['created_at']?.toString() ?? ''),
            destinationPath: path,
          );
        })
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }
}

String _timeLabel(DateTime value) {
  final date = value.toLocal();
  final now = DateTime.now();
  final elapsed = now.difference(date);
  if (elapsed.isNegative || elapsed.inMinutes < 1) return 'À l’instant';
  if (elapsed.inMinutes < 60) return 'Il y a ${elapsed.inMinutes} min';
  if (elapsed.inHours < 24 && date.day == now.day) {
    return 'Il y a ${elapsed.inHours} h';
  }
  final day = DateTime(date.year, date.month, date.day);
  final today = DateTime(now.year, now.month, now.day);
  final days = today.difference(day).inDays;
  if (days == 1) return 'Hier';
  if (days < 7) return 'Il y a ${days} jours';
  if (days < 30) return 'Il y a ${(days / 7).floor()} semaines';
  if (days < 365) return 'Il y a ${(days / 30).floor()} mois';
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
}
