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
  });

  static const listProjectionKind = 'notification.list';
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

  SyncSourceDefinition listSource() => SyncSourceDefinition(
    sourceKey: 'notifications',
    owner: 'Notifications',
    path: 'api/v1/notifications/',
    projectionKind: listProjectionKind,
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

  Stream<StoredProjection?> watchList() =>
      store.watchProjection(listProjectionKind);

  Future<StoredProjection?> readList() =>
      store.readProjection(listProjectionKind);

  Stream<StoredProjection?> watchPreferences() =>
      store.watchProjection(preferencesProjectionKind);

  Future<StoredProjection?> readPreferences() =>
      store.readProjection(preferencesProjectionKind);

  Stream<OwnerSourceState> watchListSource() => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'notifications',
  );

  Future<OwnerSourceState> readListSource() => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'notifications',
  );

  Future<void> refreshList() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Notifications owner is not configured.');
    }
    await engine.pullSource(listSource());
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
  Future<bool> loadMore() async {
    if (_loadingMore) return false;
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Notifications owner is not configured.');
    }
    final original = await readList();
    final continuation = original?.payload['next'];
    if (continuation is! String || continuation.isEmpty) return false;
    final uri = Uri.tryParse(continuation);
    if (uri == null ||
        uri.path != '/api/v1/notifications/' ||
        !uri.queryParameters.containsKey('cursor') ||
        uri.queryParameters.keys.any((key) => key != 'cursor' && key != 'filter')) {
      throw const FormatException('Invalid Notifications continuation.');
    }
    final cursor = uri.queryParameters['cursor'];
    if (cursor == null || cursor.isEmpty) {
      throw const FormatException('Missing Notifications cursor.');
    }

    _loadingMore = true;
    try {
      final answer = await engine.api.get(
        'api/v1/notifications/?cursor=${Uri.encodeQueryComponent(cursor)}',
      );
      final page = answer.jsonObject();
      if (page['results'] is! List || page['count'] is! num) {
        throw const FormatException('Invalid Notifications page.');
      }
      final current = await readList();
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
        kind: listProjectionKind,
        schemaVersion: current.schemaVersion,
        payload: {
          ...current.payload,
          ...page,
          'results': merged,
        },
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
    final current = await readList();
    final rows = current?.payload['results'];
    if (current == null || rows is! List) return;
    var changed = 0;
    final now = DateTime.now().toUtc().toIso8601String();
    final nextRows = rows.map((value) {
      if (value is! Map) return value;
      if (id != null && value['id']?.toString() != id) return value;
      if (value['is_read'] == true) return value;
      changed++;
      return {...value, 'is_read': true, 'read_at': now};
    }).toList(growable: false);
    final unread = current.payload['unread_count'];
    await store.putProjection(
      kind: listProjectionKind,
      schemaVersion: current.schemaVersion,
      payload: {
        ...current.payload,
        'results': nextRows,
        if (id == null) 'unread_count': 0,
        if (id != null && unread is num)
          'unread_count': (unread.toInt() - changed).clamp(0, 1 << 30),
      },
      sourceGeneratedAt: current.sourceGeneratedAt,
      sourceUpdatedAt: current.sourceUpdatedAt,
      freshnessPolicyId: listFreshness.id,
    );
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
