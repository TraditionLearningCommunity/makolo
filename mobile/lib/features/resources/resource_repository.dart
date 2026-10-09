import 'package:drift/drift.dart';

import '../../data/files/resource_download_destination.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class ResourceSourceState {
  const ResourceSourceState({
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

  static const unknown = ResourceSourceState();
}

class ResourceReuseResult {
  const ResourceReuseResult({
    required this.journeyId,
    required this.artifactId,
  });

  final String journeyId;
  final String artifactId;
}

class ResourceRepository {
  ResourceRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
    this.api,
  });

  static const collectionProjectionKind = 'personal.me.resources';
  static const detailProjectionKind = 'personal.resource.detail';
  static const defaultLimit = 24;
  static const versionLimit = 24;
  static const freshnessPolicy = FreshnessPolicy(id: 'personal-resources');

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;
  final MakoloApiClient? api;

  String collectionResourceKey({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) {
    final normalized = Uri.encodeComponent(query.trim());
    return normalized + ':' + offset.toString() + ':' + limit.toString();
  }

  String collectionSourceKey({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) =>
      'resources:' +
      collectionResourceKey(query: query, offset: offset, limit: limit);

  SyncSourceDefinition collectionSourceFor({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) {
    final encoded = Uri.encodeQueryComponent(query.trim());
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: collectionSourceKey(
        query: query,
        offset: offset,
        limit: limit,
      ),
      owner: 'PersonalAsset',
      path:
          'api/v1/me/resources/?q=' +
          encoded +
          '&limit=' +
          limit.toString() +
          '&offset=' +
          offset.toString(),
      projectionKind: collectionProjectionKind,
      resourceKey: collectionResourceKey(
        query: query,
        offset: offset,
        limit: limit,
      ),
      category: SyncSourceCategory.collection,
      freshnessPolicy: freshnessPolicy,
    );
  }

  SyncSourceDefinition detailSourceFor(String assetId) =>
      SyncSourceDefinition.projectionEnvelope(
        sourceKey: 'resource:' + assetId,
        owner: 'PersonalAsset',
        path:
            'api/v1/me/resources/' +
            Uri.encodeComponent(assetId) +
            '/?version_limit=' +
            versionLimit.toString(),
        projectionKind: detailProjectionKind,
        resourceKey: assetId,
        category: SyncSourceCategory.keyedDetail,
        freshnessPolicy: freshnessPolicy,
      );

  Stream<List<StoredProjection>> watchCollectionPages() =>
      store.watchProjections(collectionProjectionKind);

  Stream<StoredProjection?> watchDetail(String assetId) =>
      store.watchProjection(detailProjectionKind, resourceKey: assetId);

  Future<StoredProjection?> readCollectionPage({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) => store.readProjection(
    collectionProjectionKind,
    resourceKey: collectionResourceKey(
      query: query,
      offset: offset,
      limit: limit,
    ),
  );

  Future<void> refreshCollectionPage({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    await engine.refreshSource(
      collectionSourceFor(query: query, offset: offset, limit: limit),
    );
  }

  Future<void> refreshDetail(String assetId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    await engine.refreshSource(detailSourceFor(assetId));
  }

  Stream<ResourceSourceState> watchCollectionSource({
    required String query,
    int offset = 0,
    int limit = defaultLimit,
  }) => _watchSource(
    collectionSourceKey(query: query, offset: offset, limit: limit),
  );

  Stream<ResourceSourceState> watchDetailSource(String assetId) =>
      _watchSource('resource:' + assetId);

  Stream<ResourceSourceState> _watchSource(String sourceKey) {
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? ResourceSourceState.unknown
          : ResourceSourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<void> downloadVersionToLocal({
    required String path,
    required String assetId,
    required String title,
    required int versionNumber,
    TransferProgress? onProgress,
  }) async {
    final destination = await resourceDownloadDestination(
      profileId: profileId,
      assetId: assetId,
      title: title,
      versionNumber: versionNumber,
    );
    await downloadVersion(
      path: path,
      destinationPath: destination,
      onProgress: onProgress,
    );
  }

  Future<void> downloadVersion({
    required String path,
    required String destinationPath,
    TransferProgress? onProgress,
  }) async {
    final client = api;
    if (client == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    await client.download(
      _relative(path),
      destinationPath: destinationPath,
      onProgress: onProgress,
    );
  }

  Future<ResourceReuseResult> reuseVersion({
    required String path,
    required String journeyId,
  }) async {
    final client = api;
    if (client == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    final response = await client.post(
      _relative(path),
      body: {'journey_id': journeyId},
    );
    final envelope = response.jsonObject();
    final data = _map(envelope['data']);
    final result = _map(data['result']);
    final returnedJourney = _string(result['journey_id']);
    final artifact = _string(result['id']);
    if (returnedJourney == null || artifact == null) {
      throw const FormatException('Invalid PersonalAsset reuse response.');
    }
    return ResourceReuseResult(
      journeyId: returnedJourney,
      artifactId: artifact,
    );
  }

  String _relative(String path) =>
      path.startsWith('/') ? path.substring(1) : path;
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}
