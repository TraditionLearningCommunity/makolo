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
    await engine.refreshSource(listSource());
  }

  Future<void> refreshPreferences() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote notification preferences are not configured.');
    }
    await engine.refreshSource(preferencesSource());
  }

  Future<void> markRead(String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour marquer cette notification comme lue.',
      );
    }
    await engine.api.post('api/v1/notifications/$id/read/');
    await refreshList();
  }

  Future<void> markAllRead() async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour marquer les notifications comme lues.',
      );
    }
    await engine.api.post('api/v1/notifications/read-all/');
    await refreshList();
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
