import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/api_error.dart';
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
    final matches = stored
        .where(
          (row) =>
              row.schemaVersion == 1 &&
              (row.payload['query']?.toString().trim().toLowerCase() ?? '') ==
                  normalized &&
              row.payload['filter'] == type &&
              row.payload['items'] is List,
        )
        .toList();
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

  /// Explicitly prepare the next not-yet-received pages. Every existing
  /// snapshot stays durable and can be reused on the next call. The finite
  /// acquisition budget limits network work, never the retained History.
  /// Returns true only after the owner has actually reported its final page.
  Future<bool> prepareHistoryOffline({
    int maxNewPages = 24,
    bool Function()? shouldContinue,
    void Function(int pagesKnown)? onProgress,
  }) async {
    if (maxNewPages < 1) throw ArgumentError.value(maxNewPages);
    var offset = 0;
    var acquired = 0;
    var known = 0;
    final seen = <int>{};
    while (shouldContinue?.call() ?? true) {
      if (!seen.add(offset)) return false;
      final status = await readOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: sourceKey(offset: 0, limit: defaultLimit),
      );
      if (status.invalidated) return false;

      var page = await readPage(offset: offset);
      if (page == null) {
        if (acquired >= maxNewPages) return false;
        acquired++;
        try {
          await refreshPage(offset: offset);
        } on Object {
          return false;
        }
        final owner = await readOwnerSourceState(
          database: database,
          profileId: profileId,
          sourceKey: sourceKey(offset: offset, limit: defaultLimit),
        );
        if (owner.invalidated || owner.lastErrorCode != null) return false;
        page = await readPage(offset: offset);
        if (page == null) return false;
      }
      if (page.schemaVersion != 1) return false;
      known++;
      onProgress?.call(known);
      final metadata = page.payload['page'];
      if (metadata is! Map ||
          metadata['offset'] != offset ||
          metadata['limit'] is! int ||
          (metadata['limit'] as int) < 1 ||
          metadata['has_more'] is! bool) {
        return false;
      }
      if (metadata['has_more'] == false) return true;
      offset += metadata['limit'] as int;
    }
    return false;
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
    late final Map<String, dynamic> envelope;
    try {
      final response = await api.get(path);
      envelope = response.jsonObject();
    } on MakoloApiError catch (error) {
      if (error.statusCode == 403 || error.statusCode == 404) {
        // Explicit owner withdrawal is not a transport outage. It must also
        // hide cached searches, not merely the unfiltered first page.
        if (sync != null) {
          await sync!.revoke(
            sourceFor(offset: 0),
            code: error.statusCode == 403 ? 'permission_denied' : 'not_found',
          );
        } else {
          await forgetCachedSearch(query: query, type: type);
        }
      }
      rethrow;
    }
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
    // The owner tombstone and the search snapshot use the same SQLite
    // transaction boundary. An in-flight 200 cannot follow a 403 purge.
    await database.transaction(() async {
      if (sync?.isActive == false ||
          (await readFirstPageSource()).invalidated) {
        throw StateError('History owner context withdrawn during search');
      }
      final actor = data['actor'];
      if (actor is Map &&
          actor['id'] != null &&
          actor['id'].toString() != profileId) {
        throw const FormatException('History search Profile mismatch');
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
    });
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
