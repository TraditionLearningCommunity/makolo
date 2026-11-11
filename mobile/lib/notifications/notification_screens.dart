import 'dart:async';

import 'package:flutter/material.dart';

import '../app/runtime/app_runtime.dart';
import '../data/local/profile_store.dart';
import '../design/behavior_primitives.dart';
import '../design/behavior_states.dart';
import '../design/makolo_theme.dart';
import '../design/surface_states.dart';
import '../features/settings/notification_preferences_screen.dart' as settings;
import '../presentation/projection_surface_adapter.dart';
import '../selectors/projection_selector.dart';
import '../sync/freshness.dart';
import '../sync/owner_source_state.dart';
import '../sync/sync_status.dart';
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
  int? _previousUnreadCount;
  bool _newNotificationsAvailable = false;

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
      final source = await widget.repository.readListSource(
        onlyUnread: _onlyUnread,
      );
      if (!mounted) return;
      if (local == null ||
          NotificationRepository.listFreshness.evaluate(
                local,
                now: DateTime.now(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
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

  void _noticeNewNotifications(Object? count) {
    if (count is! num) return;
    final current = count.toInt();
    final previous = _previousUnreadCount;
    _previousUnreadCount = current;
    if (previous == null ||
        current <= previous ||
        !_scroll.hasClients ||
        _scroll.offset < 120 ||
        _newNotificationsAvailable) {
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !_newNotificationsAvailable) {
        setState(() => _newNotificationsAvailable = true);
      }
    });
  }

  void _showNewNotifications() {
    if (_scroll.hasClients) {
      _scroll.animateTo(
        0,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
    }
    setState(() => _newNotificationsAvailable = false);
  }

  void _maybeLoadMore() {
    if (!mounted || _refreshing || _loadingMore || _pageFailed) return;
    if (!_scroll.hasClients || _scroll.position.extentAfter > 500) return;
    unawaited(_loadMore());
  }

  Future<void> _loadMore() async {
    if (_loadingMore || _refreshing) return;
    final requestedUnread = _onlyUnread;
    final snapshot = await widget.repository.readList(
      onlyUnread: requestedUnread,
    );
    if (!mounted || snapshot?.payload['next'] is! String) return;
    if (requestedUnread && snapshot?.payload['unread_count'] == 0) return;
    setState(() {
      _loadingMore = true;
      _pageFailed = false;
    });
    try {
      await widget.repository.loadMore(onlyUnread: requestedUnread);
    } on Object {
      if (mounted && requestedUnread == _onlyUnread) {
        setState(() => _pageFailed = true);
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _chooseFilter(bool unreadOnly) {
    if (_onlyUnread == unreadOnly) return;
    if (_scroll.hasClients) _scroll.jumpTo(0);
    setState(() {
      _onlyUnread = unreadOnly;
      _previousUnreadCount = null;
      _newNotificationsAvailable = false;
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
            final syncStatus = SyncStatusScope.maybeOf(context);
            final connectionUnavailable =
                syncStatus?.state == SyncVisualState.offline;
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
                  ? MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: available
                  // Cached content remains usable; the thin network cue
                  // already communicates a disconnected device.
                  ? (connectionUnavailable
                        ? MakoloFailureCue.none
                        : (source.lastErrorCode != null || _loadFailed)
                        ? MakoloFailureCue.recoverable
                        : MakoloFailureCue.none)
                  : (_attempted && !_refreshing)
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            final total = projection?.payload['total_count'];
            final unread = projection?.payload['unread_count'];
            _noticeNewNotifications(unread);
            final filteredCount = projection?.payload['count'];
            final remaining =
                filteredCount is num && filteredCount.toInt() > rows.length
                ? filteredCount.toInt() - rows.length
                : 0;
            WidgetsBinding.instance.addPostFrameCallback(
              (_) => _maybeLoadMore(),
            );

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
                  PopupMenuButton<String>(
                    tooltip: 'Actions des notifications',
                    onSelected: (action) {
                      if (action == 'read-all') unawaited(_markAllRead());
                      if (action == 'refresh') unawaited(_refresh());
                    },
                    itemBuilder: (_) => [
                      if (unread is num && unread > 0)
                        const PopupMenuItem(
                          value: 'read-all',
                          child: Text('Tout marquer comme lu'),
                        ),
                      const PopupMenuItem(
                        value: 'refresh',
                        child: Text('Actualiser'),
                      ),
                    ],
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: MakoloSurfaceStateView(
                  state: state,
                  initialLoading: const MakoloLoadingState(
                    label: 'Chargement des notifications…',
                  ),
                  recoverableErrorMessage: available
                      ? null
                      : 'Impossible d’afficher les notifications.',
                  empty: MakoloEmptyState(
                    title: _onlyUnread
                        ? 'Aucune notification non lue.'
                        : 'Aucune notification.',
                  ),
                  onRetry: _refresh,
                  content: Column(
                    children: [
                      if (_newNotificationsAvailable)
                        TextButton.icon(
                          key: const Key('notification-new-items'),
                          onPressed: _showNewNotifications,
                          icon: const Icon(Icons.arrow_upward_rounded),
                          label: const Text('Nouvelles notifications'),
                        ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(
                          MakoloSpacing.inner,
                          MakoloSpacing.sm,
                          MakoloSpacing.inner,
                          MakoloSpacing.sm,
                        ),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Wrap(
                            spacing: MakoloSpacing.sm,
                            runSpacing: MakoloSpacing.sm,
                            children: [
                              ChoiceChip(
                                showCheckmark: false,
                                visualDensity: VisualDensity.compact,
                                label: Text(
                                  'Toutes${total is num ? ' (${total.toInt()})' : ''}',
                                ),
                                selected: !_onlyUnread,
                                onSelected: (_) => _chooseFilter(false),
                              ),
                              ChoiceChip(
                                showCheckmark: false,
                                visualDensity: VisualDensity.compact,
                                label: Text(
                                  'Non lues${unread is num ? ' (${unread.toInt()})' : ''}',
                                ),
                                selected: _onlyUnread,
                                onSelected: (_) => _chooseFilter(true),
                              ),
                            ],
                          ),
                        ),
                      ),
                      Expanded(
                        child: RefreshIndicator(
                          onRefresh: _refresh,
                          child: ListView.builder(
                            controller: _scroll,
                            key: PageStorageKey<String>(
                              _onlyUnread
                                  ? 'notification-unread'
                                  : 'notification-all',
                            ),
                            physics: const AlwaysScrollableScrollPhysics(),
                            itemCount: visible.length + 1,
                            itemBuilder: (context, index) {
                              if (index == visible.length) {
                                if (visible.isEmpty &&
                                    !hasMore &&
                                    !_loadingMore) {
                                  return Padding(
                                    padding: const EdgeInsets.all(28),
                                    child: Center(
                                      child: Text(
                                        _onlyUnread
                                            ? 'Aucune notification non lue.'
                                            : 'Aucune notification.',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodyMedium,
                                      ),
                                    ),
                                  );
                                }
                                if (connectionUnavailable && hasMore) {
                                  return const SizedBox.shrink();
                                }
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
                                    child: Center(
                                      child: CircularProgressIndicator(),
                                    ),
                                  );
                                }
                                return Padding(
                                  padding: const EdgeInsets.all(20),
                                  child: Center(
                                    child: Text(
                                      hasMore
                                          ? '$remaining autres à afficher'
                                          : 'Aucune autre notification',
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall,
                                    ),
                                  ),
                                );
                              }
                              final row = visible[index];
                              final section = _notificationSection(
                                context,
                                row.createdAt,
                              );
                              final previousSection = index == 0
                                  ? null
                                  : _notificationSection(
                                      context,
                                      visible[index - 1].createdAt,
                                    );
                              final canInteract =
                                  row.destinationPath != null || !row.isRead;
                              return Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  if (section != previousSection)
                                    Padding(
                                      padding: const EdgeInsets.fromLTRB(
                                        MakoloSpacing.inner,
                                        MakoloSpacing.lg,
                                        MakoloSpacing.inner,
                                        MakoloSpacing.sm,
                                      ),
                                      child: Text(
                                        section,
                                        style: Theme.of(context)
                                            .textTheme
                                            .labelLarge
                                            ?.copyWith(
                                              color: Theme.of(context)
                                                  .colorScheme
                                                  .onSurfaceVariant,
                                              fontWeight: FontWeight.w700,
                                            ),
                                      ),
                                    ),
                                  Semantics(
                                    button: canInteract,
                                    label:
                                        '${row.isRead ? 'Lue. ' : 'Non lue. '}${row.title}. '
                                        '${row.confirmed ? 'Confirmée. ' : ''}${row.message}',
                                    child: InkWell(
                                      onTap: canInteract
                                          ? () => _open(row)
                                          : null,
                                      child: Padding(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: MakoloSpacing.inner,
                                          vertical: MakoloSpacing.compact,
                                        ),
                                        child: Row(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            SizedBox(
                                              width: 16,
                                              child: Padding(
                                                padding: const EdgeInsets.only(
                                                  top: 8,
                                                ),
                                                child: row.isRead
                                                    ? const SizedBox.shrink()
                                                    : Icon(
                                                        Icons.circle,
                                                        size: 8,
                                                        color: Theme.of(context)
                                                            .colorScheme
                                                            .primary,
                                                      ),
                                              ),
                                            ),
                                            _NotificationVisual(row: row),
                                            const SizedBox(width: 12),
                                            Expanded(
                                              child: Column(
                                                crossAxisAlignment:
                                                    CrossAxisAlignment.start,
                                                children: [
                                                  Text(
                                                    row.title,
                                                    style: Theme.of(context)
                                                        .textTheme
                                                        .titleSmall
                                                        ?.copyWith(
                                                          fontWeight: row.isRead
                                                              ? FontWeight.w500
                                                              : FontWeight.w700,
                                                        ),
                                                  ),
                                                  if (row
                                                      .message
                                                      .isNotEmpty) ...[
                                                    const SizedBox(height: 4),
                                                    Text(
                                                      row.message,
                                                      style: Theme.of(context)
                                                          .textTheme
                                                          .bodyMedium
                                                          ?.copyWith(
                                                            color: Theme.of(context)
                                                                .colorScheme
                                                                .onSurfaceVariant,
                                                          ),
                                                    ),
                                                  ],
                                                  if (row.confirmed ||
                                                      row.createdAt !=
                                                          null) ...[
                                                    const SizedBox(
                                                      height: MakoloSpacing.sm,
                                                    ),
                                                    Wrap(
                                                      spacing:
                                                          MakoloSpacing.compact,
                                                      crossAxisAlignment:
                                                          WrapCrossAlignment
                                                              .center,
                                                      children: [
                                                        if (row.confirmed)
                                                          Row(
                                                            mainAxisSize:
                                                                MainAxisSize
                                                                    .min,
                                                            children: [
                                                              const Icon(
                                                                Icons
                                                                    .check_circle_outline_rounded,
                                                                color:
                                                                    MakoloColors
                                                                        .success,
                                                                size: 15,
                                                              ),
                                                              const SizedBox(
                                                                width: 4,
                                                              ),
                                                              Text(
                                                                'Confirmée',
                                                                style:
                                                                    Theme.of(
                                                                          context,
                                                                        )
                                                                        .textTheme
                                                                        .labelMedium
                                                                        ?.copyWith(
                                                                          color:
                                                                              MakoloColors.success,
                                                                        ),
                                                              ),
                                                            ],
                                                          ),
                                                        if (row.createdAt !=
                                                            null)
                                                          Text(
                                                            _notificationDate(
                                                              context,
                                                              row.createdAt!,
                                                            ),
                                                            style:
                                                                Theme.of(
                                                                      context,
                                                                    )
                                                                    .textTheme
                                                                    .bodySmall
                                                                    ?.copyWith(
                                                                      color: Theme.of(
                                                                        context,
                                                                      ).colorScheme.onSurfaceVariant,
                                                                    ),
                                                          ),
                                                      ],
                                                    ),
                                                  ],
                                                ],
                                              ),
                                            ),
                                            if (row.destinationPath !=
                                                null) ...[
                                              const SizedBox(width: 8),
                                              const Icon(
                                                Icons.chevron_right_rounded,
                                              ),
                                            ],
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                  const Divider(height: 1, indent: 40),
                                ],
                              );
                            },
                          ),
                        ),
                      ),
                    ],
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

class _NotificationRow {
  const _NotificationRow({
    required this.id,
    required this.title,
    required this.message,
    required this.isRead,
    this.createdAt,
    this.destinationPath,
    this.confirmed = false,
    this.visualImageUrl,
    this.category = 'system',
  });

  final String id;
  final String title;
  final String message;
  final bool isRead;
  final DateTime? createdAt;
  final String? destinationPath;
  final bool confirmed;
  final String? visualImageUrl;
  final String category;

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
          // Present the subject already established by legacy Journey events.
          final confirmed = rawTitle == 'Confirmation Makolo'
              ? RegExp(r'^Votre démarche pour «(.+)» est confirmée[.!]?$')
                    .firstMatch(rawMessage)
              : null;
          return _NotificationRow(
            id: row['id']?.toString() ?? '',
            title:
                confirmed?.group(1)?.trim() ??
                (rawTitle == 'Confirmation Makolo'
                    ? 'Démarche confirmée'
                    : rawTitle.isEmpty
                    ? 'Notification'
                    : rawTitle),
            message: confirmed == null ? rawMessage : '',
            confirmed: confirmed != null,
            isRead: row['is_read'] == true,
            createdAt: DateTime.tryParse(row['created_at']?.toString() ?? ''),
            destinationPath: path,
            visualImageUrl: _visualUrl(row['visual']),
            category: row['category']?.toString() ?? 'system',
          );
        })
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }
}

String? _visualUrl(Object? raw) {
  if (raw is! Map || raw['kind'] != 'activity') return null;
  final value = raw['image_url'];
  if (value is! String) return null;
  final uri = Uri.tryParse(value);
  // The API is authoritative for whether a public image may be shown.
  // Never interpret arbitrary notification metadata as an image address.
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty)
    return null;
  return value;
}

class _NotificationVisual extends StatelessWidget {
  const _NotificationVisual({required this.row});

  final _NotificationRow row;

  IconData get _icon => switch (row.category) {
    'event' => Icons.event_outlined,
    'ticket' => Icons.confirmation_number_outlined,
    'payment' => Icons.payments_outlined,
    'security' => Icons.shield_outlined,
    'service' => Icons.handyman_outlined,
    'opportunity' => Icons.lightbulb_outline_rounded,
    'marketing' => Icons.campaign_outlined,
    _ => Icons.notifications_none_rounded,
  };

  @override
  Widget build(BuildContext context) {
    final url = row.visualImageUrl;
    final scheme = Theme.of(context).colorScheme;
    final fallback = ColoredBox(
      color: scheme.primaryContainer,
      child: Center(
        child: Icon(_icon, color: scheme.onPrimaryContainer, size: 25),
      ),
    );
    return Semantics(
      label: url == null
          ? 'Notification : ${row.category}'
          : 'Image de l’activité',
      image: url != null,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          width: 52,
          height: 52,
          child: url == null
              ? fallback
              : Image.network(
                  url,
                  width: 52,
                  height: 52,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => fallback,
                ),
        ),
      ),
    );
  }
}

String _notificationSection(BuildContext context, DateTime? value) {
  if (value == null) return 'Autres';
  final date = value.toLocal();
  final now = DateTime.now();
  final currentDay = DateTime(now.year, now.month, now.day);
  final itemDay = DateTime(date.year, date.month, date.day);
  final days = currentDay.difference(itemDay).inDays;
  if (days == 0) return 'Aujourd’hui';
  if (days == 1) return 'Hier';
  if (days > 1 && days < 7) return 'Cette semaine';
  return MaterialLocalizations.of(context).formatMonthYear(date);
}

String _notificationDate(BuildContext context, DateTime value) {
  final date = value.toLocal();
  final now = DateTime.now();
  if (date.year == now.year && date.month == now.month && date.day == now.day) {
    return MaterialLocalizations.of(context)
        .formatTimeOfDay(TimeOfDay.fromDateTime(date));
  }
  return MaterialLocalizations.of(context).formatMediumDate(date);
}
