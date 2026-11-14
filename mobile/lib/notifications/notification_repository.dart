import 'dart:convert';

import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../sync/freshness.dart';
import '../sync/owner_source_state.dart';
import '../sync/sync_engine.dart';
import '../sync/sync_source.dart';

class NotificationRepository {
  NotificationRepository({
    required this.database,
    required this.store,
    required this.profileId,
    required this.sync,
  }) {
    if (profileId.trim().isEmpty ||
        store.profileId != profileId ||
        !identical(store.database, database) ||
        (sync != null &&
            (sync!.profileId != profileId ||
                !identical(sync!.database, database)))) {
      throw ArgumentError(
        'Notifications must reuse the authenticated Profile store and sync',
      );
    }
  }

  static const listProjectionKind = 'notification.list';
  static const unreadProjectionKind = 'notification.unread';
  static const preferencesProjectionKind = 'notification.preferences';
  static const listFreshness = FreshnessPolicy(
    id: 'notification-list-contextual',
    refreshRecommendedAfter: Duration(minutes: 10),
    usableButOldAfter: Duration(days: 2),
  );
  static const preferencesFreshness = FreshnessPolicy(
    id: 'notification-preferences-contextual',
    refreshRecommendedAfter: Duration(hours: 6),
    usableButOldAfter: Duration(days: 7),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;
  bool _loadingMore = false;

  SyncSourceDefinition listSource({bool onlyUnread = false}) =>
      SyncSourceDefinition(
        sourceKey: onlyUnread ? 'notifications-unread' : 'notifications',
        owner: 'Notifications',
        path: onlyUnread
            ? 'api/v1/notifications/?filter=unread'
            : 'api/v1/notifications/',
        projectionKind: onlyUnread ? unreadProjectionKind : listProjectionKind,
        category: SyncSourceCategory.collection,
        freshnessPolicy: listFreshness,
        parser: (response) {
          final payload = response.jsonObject();
          if (payload['results'] is! List || payload['count'] is! num) {
            throw const FormatException(
              'Expected Notifications owner collection contract.',
            );
          }
          return AcquiredProjection(
            schemaVersion: 1,
            payload: jsonDecode(jsonEncode(payload)) as Map<String, dynamic>,
          );
        },
        applier: applyProjectionSnapshot,
      );

  SyncSourceDefinition preferencesSource() => SyncSourceDefinition(
    sourceKey: 'notification-preferences',
    owner: 'Notifications',
    path: 'api/v1/accounts/notification-preferences/',
    projectionKind: preferencesProjectionKind,
    category: SyncSourceCategory.keyedDetail,
    freshnessPolicy: preferencesFreshness,
    parser: (response) => AcquiredProjection(
      schemaVersion: 1,
      payload:
          jsonDecode(jsonEncode(response.jsonObject())) as Map<String, dynamic>,
    ),
    applier: applyProjectionSnapshot,
  );

  Stream<StoredProjection?> watchList({bool onlyUnread = false}) => store
      .watchProjection(onlyUnread ? unreadProjectionKind : listProjectionKind);

  Future<StoredProjection?> readList({bool onlyUnread = false}) => store
      .readProjection(onlyUnread ? unreadProjectionKind : listProjectionKind);

  Stream<StoredProjection?> watchPreferences() =>
      store.watchProjection(preferencesProjectionKind);

  Future<StoredProjection?> readPreferences() =>
      store.readProjection(preferencesProjectionKind);

  Stream<OwnerSourceState> watchListSource({bool onlyUnread = false}) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: onlyUnread ? 'notifications-unread' : 'notifications',
      );

  Future<OwnerSourceState> readListSource({bool onlyUnread = false}) =>
      readOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: onlyUnread ? 'notifications-unread' : 'notifications',
      );

  Future<void> refreshList({bool onlyUnread = false}) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Notifications owner is not configured.');
    }
    await engine.pullSource(listSource(onlyUnread: onlyUnread));
  }

  Future<void> refreshPreferences() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote notification preferences are not configured.');
    }
    await engine.pullSource(preferencesSource());
  }

  /// Continue a previously acquired list without using a server URL as a transport target.
  /// Only an owner-issued cursor on the same API path is accepted.
  Future<bool> loadMore({bool onlyUnread = false}) async {
    if (_loadingMore) return false;
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Notifications owner is not configured.');
    }
    final original = await readList(onlyUnread: onlyUnread);
    final continuation = original?.payload['next'];
    if (continuation is! String || continuation.isEmpty) return false;
    final uri = Uri.tryParse(continuation);
    if (uri == null ||
        uri.path != '/api/v1/notifications/' ||
        !uri.queryParameters.containsKey('cursor') ||
        uri.queryParameters.keys.any(
          (key) => key != 'cursor' && key != 'filter',
        ) ||
        (onlyUnread && uri.queryParameters['filter'] != 'unread') ||
        (!onlyUnread && uri.queryParameters.containsKey('filter'))) {
      throw const FormatException('Invalid Notifications continuation.');
    }
    final cursor = uri.queryParameters['cursor'];
    if (cursor == null || cursor.isEmpty) {
      throw const FormatException('Missing Notifications cursor.');
    }

    _loadingMore = true;
    try {
      final answer = await engine.api.get(
        'api/v1/notifications/?cursor=${Uri.encodeQueryComponent(cursor)}'
        '${onlyUnread ? '&filter=unread' : ''}',
      );
      final page = answer.jsonObject();
      if (page['results'] is! List || page['count'] is! num) {
        throw const FormatException('Invalid Notifications page.');
      }
      final current = await readList(onlyUnread: onlyUnread);
      if (current == null ||
          current.payload['next'] != continuation ||
          !current.receivedAt.isAtSameMomentAs(original!.receivedAt)) {
        return false; // A refresh or read mutation won the race.
      }
      final existing = current.payload['results'];
      if (existing is! List) {
        throw const FormatException('Invalid cached Notifications page.');
      }
      final known = <String>{};
      final merged = <Object?>[];
      for (final row in [...existing, ...(page['results'] as List)]) {
        if (row is! Map || row['id'] == null) continue;
        if (known.add(row['id'].toString())) merged.add(row);
      }
      await store.putProjection(
        kind: onlyUnread ? unreadProjectionKind : listProjectionKind,
        schemaVersion: current.schemaVersion,
        payload: {...current.payload, ...page, 'results': merged},
        sourceGeneratedAt: current.sourceGeneratedAt,
        sourceUpdatedAt: current.sourceUpdatedAt,
        freshnessPolicyId: listFreshness.id,
      );
      return true;
    } finally {
      _loadingMore = false;
    }
  }

  Future<void> _reflectRead({String? id}) async {
    final now = DateTime.now().toUtc().toIso8601String();
    for (final onlyUnread in [false, true]) {
      final kind = onlyUnread ? unreadProjectionKind : listProjectionKind;
      final current = await store.readProjection(kind);
      final rows = current?.payload['results'];
      if (current == null || rows is! List) continue;
      var changed = 0;
      final nextRows = <Object?>[];
      for (final value in rows) {
        if (value is! Map || (id != null && value['id']?.toString() != id)) {
          nextRows.add(value);
          continue;
        }
        if (value['is_read'] == true) {
          if (!onlyUnread) nextRows.add(value);
          continue;
        }
        changed++;
        if (!onlyUnread) {
          nextRows.add({...value, 'is_read': true, 'read_at': now});
        }
      }
      final unread = current.payload['unread_count'];
      final count = current.payload['count'];
      await store.putProjection(
        kind: kind,
        schemaVersion: current.schemaVersion,
        payload: {
          ...current.payload,
          'results': nextRows,
          if (id == null) 'unread_count': 0,
          if (id != null && unread is num)
            'unread_count': (unread.toInt() - changed).clamp(0, 1 << 30),
          if (onlyUnread && id == null) 'count': 0,
          if (onlyUnread && id == null) 'next': null,
          if (onlyUnread && id != null && count is num)
            'count': (count.toInt() - changed).clamp(0, 1 << 30),
        },
        sourceGeneratedAt: current.sourceGeneratedAt,
        sourceUpdatedAt: current.sourceUpdatedAt,
        freshnessPolicyId: listFreshness.id,
      );
    }
  }

  Future<void> markRead(String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour marquer cette notification comme lue.',
      );
    }
    await engine.api.post('api/v1/notifications/$id/read/');
    await _reflectRead(id: id);
  }

  Future<void> markAllRead() async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour marquer les notifications comme lues.',
      );
    }
    await engine.api.post('api/v1/notifications/read-all/');
    await _reflectRead();
  }

  Future<void> updatePreferences(Map<String, dynamic> changes) async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour modifier ces préférences.',
      );
    }
    await engine.api.patch(
      'api/v1/accounts/notification-preferences/',
      body: changes,
    );
    await refreshPreferences();
  }
}
