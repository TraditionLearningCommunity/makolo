import '../selectors/projection_selector.dart';

import 'dart:async';

import 'package:flutter/material.dart';

import '../data/local/profile_store.dart';
import '../design/behavior_states.dart';
import '../design/makolo_theme.dart';
import '../design/surface_states.dart';
import '../navigation/structured_destination_codec.dart';
import '../presentation/projection_surface_adapter.dart';
import '../sync/freshness.dart';
import '../sync/owner_source_state.dart';
import 'notification_repository.dart';

class NotificationInboxScreen extends StatefulWidget {
  const NotificationInboxScreen({
    super.key,
    required this.repository,
    required this.onOpenDestination,
  });

  final NotificationRepository repository;
  final Future<void> Function(String path) onOpenDestination;

  @override
  State<NotificationInboxScreen> createState() =>
      _NotificationInboxScreenState();
}

class _NotificationInboxScreenState extends State<NotificationInboxScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _onlyUnread = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readList();
    final source = await widget.repository.readListSource();
    if (!mounted) return;
    if (local == null ||
        NotificationRepository.listFreshness.evaluate(
              local,
              now: DateTime.now(),
              invalidated: source.invalidated,
            ) !=
            FreshnessState.fresh) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshList();
    } on Object {
      // Preserve the last locally synchronized inbox.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _markAllRead() async {
    try {
      await widget.repository.markAllRead();
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'La lecture n’a pas été confirmée. L’état serveur connu est conservé.',
          ),
        ),
      );
    }
  }

  Future<void> _open(_NotificationRow row) async {
    if (!row.isRead) {
      try {
        await widget.repository.markRead(row.id);
      } on Object {
        // The owner handoff remains independent from read state. Local unread
        // state is preserved when the server did not confirm the mutation.
      }
    }
    final path = row.destinationPath;
    if (!mounted) return;
    if (path == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cette destination n’est plus disponible.'),
        ),
      );
      return;
    }
    await widget.onOpenDestination(path);
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
                  ? visible.isEmpty
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
                title: const Text('Notifications'),
                actions: [
                  IconButton(
                    tooltip: 'Préférences de notification',
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => NotificationPreferencesScreen(
                          repository: widget.repository,
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
                empty: MakoloEmptyState(
                  title: _onlyUnread
                      ? 'Aucune notification non lue.'
                      : 'Aucune notification.',
                  body: 'Les signaux utiles apparaîtront ici lorsqu’ils auront quelque chose à vous porter.',
                ),
                onRetry: _refresh,
                content: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(
                        MakoloSpacing.inner,
                        MakoloSpacing.sm,
                        MakoloSpacing.inner,
                        MakoloSpacing.sm,
                      ),
                      child: Row(
                        children: [
                          ChoiceChip(
                            label: const Text('Toutes'),
                            selected: !_onlyUnread,
                            onSelected: (_) =>
                                setState(() => _onlyUnread = false),
                          ),
                          const SizedBox(width: MakoloSpacing.sm),
                          ChoiceChip(
                            label: const Text('Non lues'),
                            selected: _onlyUnread,
                            onSelected: (_) =>
                                setState(() => _onlyUnread = true),
                          ),
                          const Spacer(),
                          if (rows.any((row) => !row.isRead))
                            TextButton(
                              onPressed: _markAllRead,
                              child: const Text('Tout marquer comme lu'),
                            ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: ListView.separated(
                        key: const PageStorageKey<String>(
                          'notification-inbox-list',
                        ),
                        itemCount: visible.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (context, index) {
                          final row = visible[index];
                          return Semantics(
                            button: true,
                            label:
                                (row.isRead ? 'Lue. ' : 'Non lue. ') +
                                row.title +
                                '. ' +
                                row.message,
                            child: ListTile(
                              onTap: () => _open(row),
                              leading: ExcludeSemantics(
                                child: Icon(
                                  row.isRead
                                      ? Icons.notifications_none_outlined
                                      : Icons.circle,
                                  size: row.isRead ? 22 : 9,
                                ),
                              ),
                              title: Text(
                                row.title,
                                style: TextStyle(
                                  fontWeight: row.isRead
                                      ? FontWeight.w500
                                      : FontWeight.w700,
                                ),
                              ),
                              subtitle: Text(
                                row.message +
                                    (row.createdAt == null
                                        ? ''
                                        : '\n' + _timeLabel(row.createdAt!)),
                                maxLines: 3,
                                overflow: TextOverflow.ellipsis,
                              ),
                              trailing: const Icon(Icons.chevron_right_rounded),
                            ),
                          );
                        },
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

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key, required this.repository});

  final NotificationRepository repository;

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  Map<String, dynamic>? _draft;
  bool _loading = true;
  bool _saving = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    try {
      final local = await widget.repository.readPreferences();
      if (local != null) {
        _draft = Map<String, dynamic>.from(local.payload);
      }
      await widget.repository.refreshPreferences();
      final fresh = await widget.repository.readPreferences();
      if (fresh != null) _draft = Map<String, dynamic>.from(fresh.payload);
    } on Object {
      // Existing local preferences remain usable as the last server-known state.
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _bool(String key, {bool fallback = false}) =>
      _draft?[key] is bool ? _draft![key] as bool : fallback;

  void _setBool(String key, bool value) {
    setState(() {
      _draft ??= <String, dynamic>{};
      _draft![key] = value;
      _message = null;
    });
  }

  TimeOfDay? _time(String key) {
    final value = _draft?[key]?.toString();
    if (value == null || value.length < 5) return null;
    final parts = value.split(':');
    if (parts.length < 2) return null;
    final hour = int.tryParse(parts[0]);
    final minute = int.tryParse(parts[1]);
    if (hour == null || minute == null) return null;
    return TimeOfDay(hour: hour, minute: minute);
  }

  Future<void> _pickTime(String key) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time(key) ?? TimeOfDay.now(),
    );
    if (picked == null) return;
    setState(() {
      _draft ??= <String, dynamic>{};
      _draft![key] =
          picked.hour.toString().padLeft(2, '0') +
          ':' +
          picked.minute.toString().padLeft(2, '0') +
          ':00';
    });
  }

  Future<void> _save() async {
    final draft = _draft;
    if (_saving || draft == null) return;
    if (_bool('quiet_hours_enabled') &&
        (_time('quiet_hours_start') == null ||
            _time('quiet_hours_end') == null)) {
      setState(
        () =>
            _message = 'Choisissez le début et la fin des heures silencieuses.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.repository.updatePreferences({
        'push_notifications': _bool('push_notifications', fallback: true),
        'email_notifications': _bool('email_notifications', fallback: true),
        'security_notifications': _bool(
          'security_notifications',
          fallback: true,
        ),
        'event_notifications': _bool('event_notifications', fallback: true),
        'service_notifications': _bool('service_notifications', fallback: true),
        'opportunity_notifications': _bool(
          'opportunity_notifications',
          fallback: true,
        ),
        'marketing_notifications': _bool('marketing_notifications'),
        'quiet_hours_enabled': _bool('quiet_hours_enabled'),
        'quiet_hours_start': draft['quiet_hours_start'],
        'quiet_hours_end': draft['quiet_hours_end'],
      });
      if (mounted) setState(() => _message = 'Préférences enregistrées.');
    } on Object {
      if (mounted) {
        setState(
          () => _message = 'Les préférences n’ont pas été confirmées. Réessayez lorsque Makolo est joignable.',
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _draft == null) {
      return const Scaffold(
        body: MakoloLoadingState(label: 'Chargement des préférences…'),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Préférences')),
      body: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        children: [
          Text('Canaux', style: Theme.of(context).textTheme.titleMedium),
          SwitchListTile(
            title: const Text('Push'),
            subtitle: const Text(
              'Les alertes système restent un transport ; l’inbox Makolo conserve les signaux.',
            ),
            value: _bool('push_notifications', fallback: true),
            onChanged: (value) => _setBool('push_notifications', value),
          ),
          SwitchListTile(
            title: const Text('Email'),
            value: _bool('email_notifications', fallback: true),
            onChanged: (value) => _setBool('email_notifications', value),
          ),
          const Divider(),
          Text('Catégories', style: Theme.of(context).textTheme.titleMedium),
          _preferenceSwitch(
            'Sécurité',
            'security_notifications',
            fallback: true,
          ),
          _preferenceSwitch(
            'Événements',
            'event_notifications',
            fallback: true,
          ),
          _preferenceSwitch(
            'Services',
            'service_notifications',
            fallback: true,
          ),
          _preferenceSwitch(
            'Opportunités',
            'opportunity_notifications',
            fallback: true,
          ),
          _preferenceSwitch('Marketing', 'marketing_notifications'),
          const Divider(),
          SwitchListTile(
            title: const Text('Heures silencieuses'),
            subtitle: const Text(
              'Les livraisons non urgentes attendent ; les vérités métier ne disparaissent pas.',
            ),
            value: _bool('quiet_hours_enabled'),
            onChanged: (value) => _setBool('quiet_hours_enabled', value),
          ),
          if (_bool('quiet_hours_enabled')) ...[
            ListTile(
              title: const Text('Début'),
              subtitle: Text(
                _time('quiet_hours_start')?.format(context) ?? 'Choisir',
              ),
              onTap: () => _pickTime('quiet_hours_start'),
            ),
            ListTile(
              title: const Text('Fin'),
              subtitle: Text(
                _time('quiet_hours_end')?.format(context) ?? 'Choisir',
              ),
              onTap: () => _pickTime('quiet_hours_end'),
            ),
          ],
          if (_message != null) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(_message!),
          ],
          const SizedBox(height: MakoloSpacing.md),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? 'Enregistrement…' : 'Enregistrer'),
          ),
        ],
      ),
    );
  }

  Widget _preferenceSwitch(String label, String key, {bool fallback = false}) =>
      SwitchListTile(
        title: Text(label),
        value: _bool(key, fallback: fallback),
        onChanged: (value) => _setBool(key, value),
      );
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
    const codec = StructuredDestinationCodec();
    return raw
        .whereType<Map>()
        .map((item) {
          final row = item.map((key, value) => MapEntry(key.toString(), value));
          final destination = codec.fromNavigation(row['navigation']);
          String? path;
          if (destination != null) {
            path = switch (destination.kind.toLowerCase()) {
              'conversation' => '/conversations/' + destination.id,
              'journey' => '/journeys/' + destination.id,
              'activity' => '/activities/' + destination.id,
              'occurrence' => '/occurrences/' + destination.id,
              'access' => '/accesses/' + destination.id,
              'dossier' => '/dossiers/' + destination.id,
              'project' => '/projects/' + destination.id,
              'group' => '/groups/' + destination.id,
              _ => null,
            };
          }
          return _NotificationRow(
            id: row['id']?.toString() ?? '',
            title: row['title']?.toString().trim().isNotEmpty == true
                ? row['title'].toString().trim()
                : 'Notification',
            message: row['message']?.toString().trim() ?? '',
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
  final local = value.toLocal();
  String two(int part) => part.toString().padLeft(2, '0');
  return two(local.day) +
      '/' +
      two(local.month) +
      '/' +
      local.year.toString() +
      ' · ' +
      two(local.hour) +
      ':' +
      two(local.minute);
}
