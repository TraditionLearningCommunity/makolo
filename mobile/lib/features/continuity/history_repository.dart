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
      'offset:$offset:limit:$limit';

  String sourceKey({required int offset, required int limit}) =>
      'history:$offset:$limit';

  SyncSourceDefinition sourceFor({
    required int offset,
    int limit = defaultLimit,
  }) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: sourceKey(offset: offset, limit: limit),
      owner: 'ProfileHistory',
      path: 'api/v1/me/history/?limit=$limit&offset=$offset',
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

  Future<Map<String, dynamic>> searchPage({
    required String query,
    String type = 'all',
    int offset = 0,
    int limit = defaultLimit,
  }) async {
    final api = sync?.api;
    if (api == null) {
      throw StateError('Remote History owner is not configured.');
    }
    final path = Uri(
      path: 'api/v1/me/history/',
      queryParameters: {
        if (query.trim().isNotEmpty) 'q': query.trim(),
        'type': type,
        'limit': '$limit',
        'offset': '$offset',
      },
    ).toString();
    final response = await api.get(path);
    final envelope = response.jsonObject();
    if (envelope['meta'] is! Map ||
        (envelope['meta'] as Map)['projection'] != projectionKind ||
        envelope['data'] is! Map) {
      throw const FormatException('Invalid personal History projection.');
    }
    return Map<String, dynamic>.from(envelope['data'] as Map);
  }

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
