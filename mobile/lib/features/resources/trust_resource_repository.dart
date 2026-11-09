import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

enum TrustResourceFamily {
  proofs,
  titles;

  String get segment => this == TrustResourceFamily.proofs ? 'proofs' : 'titles';
  String get collectionProjection => this == TrustResourceFamily.proofs
      ? 'personal.proofs'
      : 'personal.titles';
  String get detailProjection => this == TrustResourceFamily.proofs
      ? 'personal.proof.detail'
      : 'personal.title.detail';
  String get indexedKind =>
      this == TrustResourceFamily.proofs ? 'Proof' : 'Credential';
}

class TrustResourceSourceState {
  const TrustResourceSourceState({
    this.lastSuccessAt,
    this.invalidated = false,
    this.lastErrorCode,
  });

  final DateTime? lastSuccessAt;
  final bool invalidated;
  final String? lastErrorCode;

  ReachabilityState get reachability => reachabilityFromSource(
    lastSuccessAt: lastSuccessAt,
    lastErrorCode: lastErrorCode,
  );

  static const unknown = TrustResourceSourceState();
}

class TrustResourceRepository {
  TrustResourceRepository({
    required this.database,
    required this.store,
    required this.profileId,
    required this.sync,
  });

  static const defaultLimit = 24;
  static const freshnessPolicy = FreshnessPolicy(id: 'personal-trust-resources');

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  String collectionScopeKey({
    required TrustResourceFamily family,
    required String query,
    required String status,
    required String type,
    required String sort,
  }) => Uri.encodeComponent(
    [family.segment, query.trim(), status, type, sort].join('|'),
  );

  String collectionResourceKey({
    required TrustResourceFamily family,
    required String query,
    required String status,
    required String type,
    required String sort,
    required int offset,
    int limit = defaultLimit,
  }) =>
      '${collectionScopeKey(family: family, query: query, status: status, type: type, sort: sort)}:$offset:$limit';

  String collectionSourceKey({
    required TrustResourceFamily family,
    required String query,
    required String status,
    required String type,
    required String sort,
    required int offset,
    int limit = defaultLimit,
  }) =>
      'trust:${collectionResourceKey(family: family, query: query, status: status, type: type, sort: sort, offset: offset, limit: limit)}';

  String detailSourceKey(TrustResourceFamily family, String id) =>
      'trust:${family.segment}:$id';

  SyncSourceDefinition collectionSourceFor({
    required TrustResourceFamily family,
    required String query,
    String status = 'all',
    String type = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) {
    final params = <String, String>{
      if (query.trim().isNotEmpty) 'q': query.trim(),
      'status': status,
      if (type.isNotEmpty) 'type': type,
      'sort': sort,
      'limit': '$limit',
      'offset': '$offset',
    };
    final queryString = Uri(queryParameters: params).query;
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: collectionSourceKey(
        family: family,
        query: query,
        status: status,
        type: type,
        sort: sort,
        offset: offset,
        limit: limit,
      ),
      owner: 'Trust',
      path: 'api/v1/me/${family.segment}/?$queryString',
      projectionKind: family.collectionProjection,
      resourceKey: collectionResourceKey(
        family: family,
        query: query,
        status: status,
        type: type,
        sort: sort,
        offset: offset,
        limit: limit,
      ),
      category: SyncSourceCategory.collection,
      freshnessPolicy: freshnessPolicy,
    );
  }

  SyncSourceDefinition detailSourceFor(
    TrustResourceFamily family,
    String id,
  ) => SyncSourceDefinition.projectionEnvelope(
    sourceKey: detailSourceKey(family, id),
    owner: 'Trust',
    path: 'api/v1/me/${family.segment}/${Uri.encodeComponent(id)}/',
    projectionKind: family.detailProjection,
    resourceKey: id,
    indexedResourceKind: family.indexedKind,
    category: SyncSourceCategory.keyedDetail,
    freshnessPolicy: freshnessPolicy,
  );

  Stream<List<StoredProjection>> watchCollectionPages(
    TrustResourceFamily family,
  ) => store.watchProjections(family.collectionProjection);

  Stream<StoredProjection?> watchDetail(
    TrustResourceFamily family,
    String id,
  ) => store.watchProjection(family.detailProjection, resourceKey: id);

  Future<StoredProjection?> readCollectionPage({
    required TrustResourceFamily family,
    required String query,
    String status = 'all',
    String type = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) => store.readProjection(
    family.collectionProjection,
    resourceKey: collectionResourceKey(
      family: family,
      query: query,
      status: status,
      type: type,
      sort: sort,
      offset: offset,
      limit: limit,
    ),
  );

  Future<StoredProjection?> readDetail(
    TrustResourceFamily family,
    String id,
  ) => store.readProjection(family.detailProjection, resourceKey: id);

  Future<void> refreshCollectionPage({
    required TrustResourceFamily family,
    required String query,
    String status = 'all',
    String type = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Trust owner is not configured.');
    }
    await engine.refreshSource(
      collectionSourceFor(
        family: family,
        query: query,
        status: status,
        type: type,
        sort: sort,
        offset: offset,
        limit: limit,
      ),
    );
  }

  Future<void> refreshDetail(TrustResourceFamily family, String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Trust owner is not configured.');
    }
    await engine.refreshSource(detailSourceFor(family, id));
  }

  Future<TrustResourceSourceState> readCollectionSource({
    required TrustResourceFamily family,
    required String query,
    String status = 'all',
    String type = '',
    String sort = 'recent',
    int offset = 0,
    int limit = defaultLimit,
  }) async {
    final key = collectionSourceKey(
      family: family,
      query: query,
      status: status,
      type: type,
      sort: sort,
      offset: offset,
      limit: limit,
    );
    final row =
        await (database.select(database.syncSources)..where(
              (item) =>
                  item.profileId.equals(profileId) &
                  item.sourceKey.equals(key),
            ))
            .getSingleOrNull();
    return row == null
        ? TrustResourceSourceState.unknown
        : TrustResourceSourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  Stream<TrustResourceSourceState> watchCollectionSource({
    required TrustResourceFamily family,
    required String query,
    String status = 'all',
    String type = '',
    String sort = 'recent',
    int offset = 0,
    int limit = defaultLimit,
  }) => _watchSource(
    collectionSourceKey(
      family: family,
      query: query,
      status: status,
      type: type,
      sort: sort,
      offset: offset,
      limit: limit,
    ),
  );

  Stream<TrustResourceSourceState> watchDetailSource(
    TrustResourceFamily family,
    String id,
  ) => _watchSource(detailSourceKey(family, id));

  Stream<TrustResourceSourceState> _watchSource(String sourceKey) {
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? TrustResourceSourceState.unknown
          : TrustResourceSourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }
}
