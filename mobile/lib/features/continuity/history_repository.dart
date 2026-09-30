import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class HistoryRepository {
  HistoryRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'personal.history';
  static const defaultLimit = 24;
  static const freshnessPolicy = FreshnessPolicy(
    id: 'history-stable',
    refreshRecommendedAfter: Duration(hours: 6),
    usableButOldAfter: Duration(days: 30),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  String resourceKey({required int offset, required int limit}) =>
      'offset:\$offset:limit:\$limit';

  String sourceKey({required int offset, required int limit}) =>
      'history:\$offset:\$limit';

  SyncSourceDefinition sourceFor({
    required int offset,
    int limit = defaultLimit,
  }) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: sourceKey(offset: offset, limit: limit),
      owner: 'ProfileHistory',
      path: 'api/v1/me/history/?limit=\$limit&offset=\$offset',
      projectionKind: projectionKind,
      resourceKey: resourceKey(offset: offset, limit: limit),
      category: SyncSourceCategory.collection,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<List<StoredProjection>> watchCachedPages() =>
      store.watchProjections(projectionKind);

  Future<StoredProjection?> readPage({
    required int offset,
    int limit = defaultLimit,
  }) => store.readProjection(
    projectionKind,
    resourceKey: resourceKey(offset: offset, limit: limit),
  );

  Stream<OwnerSourceState> watchFirstPageSource() => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: sourceKey(offset: 0, limit: defaultLimit),
  );

  Future<OwnerSourceState> readFirstPageSource() => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: sourceKey(offset: 0, limit: defaultLimit),
  );

  Future<void> refreshPage({
    required int offset,
    int limit = defaultLimit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote History owner is not configured.');
    }
    await engine.refreshSource(sourceFor(offset: offset, limit: limit));
  }
}
