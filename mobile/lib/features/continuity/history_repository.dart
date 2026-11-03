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
  static const searchProjectionKind = 'personal.history.search';
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

  /// Owner search pages are different from the unfiltered history. Their
  /// query keys are Profile-scoped, so one search never replaces another.
  static String searchResourceKey({
    required String query,
    required String type,
    required int offset,
    int limit = defaultLimit,
  }) => Uri(
    queryParameters: {
      'q': query.trim().toLowerCase(),
      'type': type,
      'offset': '$offset',
      'limit': '$limit',
    },
  ).query;

  Future<List<StoredProjection>> readCachedSearchPages({
    required String query,
    required String type,
  }) async {
    final source = await readFirstPageSource();
    if (source.invalidated) return const [];
    final normalized = query.trim().toLowerCase();
    final stored = await store.readProjections(searchProjectionKind);
    final matches = stored.where((row) =>
      row.schemaVersion == 1 &&
      (row.payload['query']?.toString().trim().toLowerCase() ?? '') ==
          normalized &&
      row.payload['filter'] == type &&
      row.payload['items'] is List).toList();
    matches.sort((a, b) {
      final aa = _pageOffset(a.payload);
      final bb = _pageOffset(b.payload);
      return aa.compareTo(bb);
    });
    return matches;
  }

  Future<void> forgetCachedSearch({
    required String query,
    required String type,
  }) async {
    final pages = await readCachedSearchPages(query: query, type: type);
    for (final page in pages) {
      await store.deleteProjection(
        searchProjectionKind,
        resourceKey: page.resourceKey,
      );
    }
  }

  static int _pageOffset(Map<String, dynamic> payload) {
    final page = payload['page'];
    if (page is Map && page['offset'] is num) {
      return (page['offset'] as num).toInt();
    }
    return 0;
  }

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
    final data = Map<String, dynamic>.from(envelope['data'] as Map);
    final expectedQuery = query.trim().toLowerCase();
    final receivedQuery = data['query']?.toString().trim().toLowerCase() ?? '';
    if (data['filter'] != type ||
        receivedQuery != expectedQuery ||
        data['items'] is! List ||
        _pageOffset(data) != offset) {
      throw const FormatException('History search owner response mismatched');
    }
    await store.putProjection(
      kind: searchProjectionKind,
      resourceKey: searchResourceKey(
        query: query,
        type: type,
        offset: offset,
        limit: limit,
      ),
      schemaVersion: 1,
      payload: data,
    );
    return data;
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
