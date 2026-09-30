import 'dart:convert';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class ConversationRepository {
  ConversationRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const listProjectionKind = 'conversation.list';
  static const detailProjectionKind = 'conversation.detail';
  static const listFreshness = FreshnessPolicy(
    id: 'conversation-list-contextual',
    refreshRecommendedAfter: Duration(minutes: 15),
    usableButOldAfter: Duration(days: 2),
  );
  static const detailFreshness = FreshnessPolicy(
    id: 'conversation-detail-contextual',
    refreshRecommendedAfter: Duration(minutes: 10),
    usableButOldAfter: Duration(days: 2),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition listSource() => SyncSourceDefinition(
        sourceKey: 'conversations',
        owner: 'Conversations',
        path: 'api/v1/conversations/?limit=50',
        projectionKind: listProjectionKind,
        category: SyncSourceCategory.collection,
        freshnessPolicy: listFreshness,
        parser: (response) {
          final payload = response.jsonObject();
          if (payload['results'] is! List || payload['count'] is! num) {
            throw const FormatException(
              'Expected Conversations owner collection contract.',
            );
          }
          return AcquiredProjection(schemaVersion: 1, payload: payload);
        },
        applier: applyProjectionSnapshot,
      );

  SyncSourceDefinition detailSource(String id) => SyncSourceDefinition(
        sourceKey: 'conversation:' + id,
        owner: 'Conversations',
        path: 'api/v1/conversations/' + id + '/',
        projectionKind: detailProjectionKind,
        resourceKey: id,
        category: SyncSourceCategory.keyedDetail,
        freshnessPolicy: detailFreshness,
        parser: (response) {
          final payload = response.jsonObject();
          if (payload['id']?.toString() != id || payload['points'] is! List) {
            throw const FormatException(
              'Expected Conversations owner detail contract.',
            );
          }
          return AcquiredProjection(
            schemaVersion: 1,
            payload: jsonDecode(jsonEncode(payload)) as Map<String, dynamic>,
          );
        },
        applier: applyProjectionSnapshot,
      );

  Stream<StoredProjection?> watchList() =>
      store.watchProjection(listProjectionKind);

  Future<StoredProjection?> readList() =>
      store.readProjection(listProjectionKind);

  Stream<StoredProjection?> watchDetail(String id) =>
      store.watchProjection(detailProjectionKind, resourceKey: id);

  Future<StoredProjection?> readDetail(String id) =>
      store.readProjection(detailProjectionKind, resourceKey: id);

  Stream<OwnerSourceState> watchListSource() => watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'conversations',
      );

  Future<OwnerSourceState> readListSource() => readOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'conversations',
      );

  Stream<OwnerSourceState> watchDetailSource(String id) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'conversation:' + id,
      );

  Future<OwnerSourceState> readDetailSource(String id) =>
      readOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'conversation:' + id,
      );

  Future<void> refreshList() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    await engine.refreshSource(listSource());
  }

  Future<void> refreshDetail(String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    await engine.refreshSource(detailSource(id));
  }
}
