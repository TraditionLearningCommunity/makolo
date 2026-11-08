import 'dart:io';

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
    return '$normalized:$offset:$limit';
  }

  String collectionSourceKey({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) =>
      'resources:${collectionResourceKey(query: query, offset: offset, limit: limit)}';

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
      path: 'api/v1/me/resources/?q=$encoded&limit=$limit&offset=$offset',
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

  SyncSourceDefinition detailSourceFor(
    String assetId,
  ) => SyncSourceDefinition.projectionEnvelope(
    sourceKey: 'resource:$assetId',
    owner: 'PersonalAsset',
    path:
        'api/v1/me/resources/${Uri.encodeComponent(assetId)}/?version_limit=$versionLimit',
    projectionKind: detailProjectionKind,
    resourceKey: assetId,
    indexedResourceKind: 'PersonalAsset',
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

  Future<StoredProjection?> readDetail(String assetId) =>
      store.readProjection(detailProjectionKind, resourceKey: assetId);

  /// Metadata only. Never download resource bytes without explicit intent.
  /// Owners enforce access independently for each keyed resource.
  Future<void> warmKnownDetails(
    Iterable<String> assetIds, {
    int limit = 8,
  }) async {
    if (sync == null) return;
    final seen = <String>{};
    var acquired = 0;
    for (final assetId in assetIds) {
      if (assetId.isEmpty || !seen.add(assetId)) continue;
      if (acquired >= limit) break;
      if (await readDetail(assetId) != null) continue;
      acquired++;
      try {
        await refreshDetail(assetId);
        final status = await readDetailSource(assetId);
        if (status.reachability == ReachabilityState.unreachable) break;
      } on Object {
        // An unreachable owner must not trigger a chain of more requests.
        break;
      }
    }
  }

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

  Future<ResourceSourceState> readCollectionSource({
    required String query,
    int offset = 0,
    int limit = defaultLimit,
  }) async {
    final key = collectionSourceKey(query: query, offset: offset, limit: limit);
    final rows =
        await (database.select(database.syncSources)..where(
              (row) =>
                  row.profileId.equals(profileId) & row.sourceKey.equals(key),
            ))
            .getSingleOrNull();
    return rows == null
        ? ResourceSourceState.unknown
        : ResourceSourceState(
            lastSuccessAt: rows.lastSuccessAt,
            invalidated: rows.invalidated,
            lastErrorCode: rows.lastErrorCode,
          );
  }

  Stream<ResourceSourceState> watchCollectionSource({
    required String query,
    int offset = 0,
    int limit = defaultLimit,
  }) => _watchSource(
    collectionSourceKey(query: query, offset: offset, limit: limit),
  );

  Stream<ResourceSourceState> watchDetailSource(String assetId) =>
      _watchSource('resource:$assetId');

  Future<ResourceSourceState> readDetailSource(String assetId) async {
    final row =
        await (database.select(database.syncSources)..where(
              (item) =>
                  item.profileId.equals(profileId) &
                  item.sourceKey.equals('resource:$assetId'),
            ))
            .getSingleOrNull();
    return row == null
        ? ResourceSourceState.unknown
        : ResourceSourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

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

  /// Only files explicitly downloaded by this Profile are usable offline.
  /// This says nothing about current Requirement or owner validation.
  Future<bool> localVersionExists({
    required String assetId,
    required String title,
    required int versionNumber,
  }) async {
    final path = await resourceDownloadDestination(
      profileId: profileId,
      assetId: assetId,
      title: title,
      versionNumber: versionNumber,
    );
    final file = File(path);
    return await file.exists() && await file.length() > 0;
  }

  Future<void> downloadVersionToLocal({
    required String path,
    required String assetId,
    required String title,
    required int versionNumber,
    TransferProgress? onProgress,
  }) async {
    if (sync?.isActive == false ||
        (await readDetailSource(assetId)).invalidated) {
      throw StateError('Resource owner permission withdrawn');
    }
    final destination = await resourceDownloadDestination(
      profileId: profileId,
      assetId: assetId,
      title: title,
      versionNumber: versionNumber,
    );
    final retained = File(destination);
    if (await retained.exists() && await retained.length() > 0) {
      // Re-export a file consciously downloaded before: no network needed.
      return;
    }
    await downloadVersion(
      path: path,
      destinationPath: destination,
      onProgress: onProgress,
    );
    if (sync?.isActive == false ||
        (await readDetailSource(assetId)).invalidated) {
      await removeLocallyRetainedResourceVersions(
        profileId: profileId,
        assetId: assetId,
      );
      throw StateError('Resource owner permission withdrawn during transfer');
    }
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
      _relative(path, action: 'download'),
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
      _relative(path, action: 'reuse'),
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

  String _relative(String path, {required String action}) {
    final uri = Uri.tryParse(path);
    if (uri == null ||
        uri.hasScheme ||
        uri.hasAuthority ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw const FormatException('Unexpected PersonalAsset owner link');
    }
    final relative = uri.path.startsWith('/')
        ? uri.path.substring(1)
        : uri.path;
    final ownerRoute = RegExp(
      r'^api/v1/me/resources/versions/'
      r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
      r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/(download|reuse)/$',
    );
    if (!ownerRoute.hasMatch(relative) || !relative.endsWith('/$action/')) {
      throw const FormatException('PersonalAsset action path mismatch');
    }
    return relative;
  }
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
