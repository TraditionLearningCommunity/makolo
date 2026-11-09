import 'dart:io';

import 'package:drift/drift.dart';
import 'package:path/path.dart' as p;

import '../../data/files/profile_paths.dart';
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

  bool get ownerDenied =>
      invalidated &&
      (lastErrorCode == 'permission_denied' || lastErrorCode == 'not_found');

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

class ResourceOption {
  const ResourceOption({required this.id, required this.label});

  final String id;
  final String label;
}

class ResourceDocumentOptions {
  const ResourceDocumentOptions({
    required this.kinds,
    required this.sensitivities,
  });

  final List<ResourceOption> kinds;
  final List<ResourceOption> sensitivities;

  static const fallback = ResourceDocumentOptions(
    kinds: [
      ResourceOption(id: 'cv', label: 'CV'),
      ResourceOption(id: 'cover_letter', label: 'Lettre de motivation'),
      ResourceOption(id: 'certificate', label: 'Certificat'),
      ResourceOption(id: 'transcript', label: 'Relevé'),
      ResourceOption(id: 'recommendation', label: 'Recommandation'),
      ResourceOption(id: 'identity_document', label: 'Document d’identité'),
      ResourceOption(id: 'form', label: 'Formulaire'),
      ResourceOption(id: 'payment_receipt', label: 'Reçu de paiement'),
      ResourceOption(id: 'other', label: 'Autre'),
    ],
    sensitivities: [
      ResourceOption(id: 'normal', label: 'Normale'),
      ResourceOption(id: 'sensitive', label: 'Sensible'),
      ResourceOption(id: 'restricted', label: 'Restreinte'),
    ],
  );
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
  static const freshnessPolicy = FreshnessPolicy(
    id: 'personal-resources',
    refreshRecommendedAfter: Duration(hours: 2),
    usableButOldAfter: Duration(days: 7),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;
  final MakoloApiClient? api;

  String collectionScopeKey({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
  }) => Uri.encodeComponent(
    [query.trim(), view, kind, sensitivity, sort].join('|'),
  );

  String collectionResourceKey({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) =>
      '${collectionScopeKey(query: query, view: view, kind: kind, sensitivity: sensitivity, sort: sort)}:$offset:$limit';

  String _legacyCollectionResourceKey({
    required String query,
    required int offset,
    int limit = defaultLimit,
  }) {
    final normalized = Uri.encodeComponent(query.trim());
    return '$normalized:$offset:$limit';
  }

  String collectionSourceKey({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) =>
      'resources:${collectionResourceKey(query: query, view: view, kind: kind, sensitivity: sensitivity, sort: sort, offset: offset, limit: limit)}';

  SyncSourceDefinition collectionSourceFor({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) {
    final params = <String, String>{
      if (query.trim().isNotEmpty) 'q': query.trim(),
      'view': view,
      if (kind.isNotEmpty) 'kind': kind,
      if (sensitivity.isNotEmpty) 'sensitivity': sensitivity,
      'sort': sort,
      'limit': '$limit',
      'offset': '$offset',
    };
    final queryString = Uri(queryParameters: params).query;
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: collectionSourceKey(
        query: query,
        view: view,
        kind: kind,
        sensitivity: sensitivity,
        sort: sort,
        offset: offset,
        limit: limit,
      ),
      owner: 'PersonalAsset',
      path: 'api/v1/me/resources/?$queryString',
      projectionKind: collectionProjectionKind,
      resourceKey: collectionResourceKey(
        query: query,
        view: view,
        kind: kind,
        sensitivity: sensitivity,
        sort: sort,
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
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) async {
    final current = await store.readProjection(
      collectionProjectionKind,
      resourceKey: collectionResourceKey(
        query: query,
        view: view,
        kind: kind,
        sensitivity: sensitivity,
        sort: sort,
        offset: offset,
        limit: limit,
      ),
    );
    if (current != null) return current;
    if (view == 'current' &&
        kind.isEmpty &&
        sensitivity.isEmpty &&
        sort == 'recent') {
      return store.readProjection(
        collectionProjectionKind,
        resourceKey: _legacyCollectionResourceKey(
          query: query,
          offset: offset,
          limit: limit,
        ),
      );
    }
    return null;
  }

  Future<StoredProjection?> readDetail(String assetId) =>
      store.readProjection(detailProjectionKind, resourceKey: assetId);

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
        break;
      }
    }
  }

  Future<bool> shouldRefreshCollectionPage({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    int offset = 0,
    int limit = defaultLimit,
    DateTime? now,
  }) async {
    final projection = await readCollectionPage(
      query: query,
      view: view,
      kind: kind,
      sensitivity: sensitivity,
      sort: sort,
      offset: offset,
      limit: limit,
    );
    final source = await readCollectionSource(
      query: query,
      view: view,
      kind: kind,
      sensitivity: sensitivity,
      sort: sort,
      offset: offset,
      limit: limit,
    );
    if (source.ownerDenied) return false;
    if (projection == null || source.lastErrorCode != null || source.invalidated) {
      return true;
    }
    return freshnessPolicy.evaluate(
          projection,
          now: (now ?? DateTime.now()).toUtc(),
        ) !=
        FreshnessState.fresh;
  }

  Future<bool> shouldRefreshDetail(
    String assetId, {
    DateTime? now,
  }) async {
    final projection = await readDetail(assetId);
    final source = await readDetailSource(assetId);
    if (source.ownerDenied) return false;
    if (projection == null || source.lastErrorCode != null || source.invalidated) {
      return true;
    }
    return freshnessPolicy.evaluate(
          projection,
          now: (now ?? DateTime.now()).toUtc(),
        ) !=
        FreshnessState.fresh;
  }

  Future<void> ensureCollectionPage({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    int offset = 0,
    int limit = defaultLimit,
  }) async {
    if (!await shouldRefreshCollectionPage(
      query: query,
      view: view,
      kind: kind,
      sensitivity: sensitivity,
      sort: sort,
      offset: offset,
      limit: limit,
    )) {
      return;
    }
    await refreshCollectionPage(
      query: query,
      view: view,
      kind: kind,
      sensitivity: sensitivity,
      sort: sort,
      offset: offset,
      limit: limit,
    );
  }

  Future<void> ensureDetail(String assetId) async {
    if (await shouldRefreshDetail(assetId)) {
      await refreshDetail(assetId);
    }
  }

  Future<void> refreshCollectionPage({
    required String query,
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    required int offset,
    int limit = defaultLimit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    await engine.refreshSource(
      collectionSourceFor(
        query: query,
        view: view,
        kind: kind,
        sensitivity: sensitivity,
        sort: sort,
        offset: offset,
        limit: limit,
      ),
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
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    int offset = 0,
    int limit = defaultLimit,
  }) async {
    final key = collectionSourceKey(
      query: query,
      view: view,
      kind: kind,
      sensitivity: sensitivity,
      sort: sort,
      offset: offset,
      limit: limit,
    );
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
    String view = 'current',
    String kind = '',
    String sensitivity = '',
    String sort = 'recent',
    int offset = 0,
    int limit = defaultLimit,
  }) => _watchSource(
    collectionSourceKey(
      query: query,
      view: view,
      kind: kind,
      sensitivity: sensitivity,
      sort: sort,
      offset: offset,
      limit: limit,
    ),
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

  Future<ResourceDocumentOptions> documentOptions() async {
    StoredProjection? projection = await readCollectionPage(
      query: '',
      offset: 0,
    );
    if (projection == null && sync != null) {
      try {
        await refreshCollectionPage(query: '', offset: 0);
        projection = await readCollectionPage(query: '', offset: 0);
      } on Object {
        // Fall back to the canonical enum values already shipped by this app.
      }
    }
    final documents = _map(projection?.payload['documents']);
    final filterOptions = _map(documents['filter_options']);
    final kinds = _options(filterOptions['kinds']);
    final sensitivities = _options(filterOptions['sensitivities']);
    if (kinds.isEmpty || sensitivities.isEmpty) {
      return ResourceDocumentOptions.fallback;
    }
    return ResourceDocumentOptions(
      kinds: List.unmodifiable(kinds),
      sensitivities: List.unmodifiable(sensitivities),
    );
  }

  Future<String> addDocumentVersionForAsset({
    required String assetId,
    required String filePath,
    required String filename,
    required String contentType,
    DateTime? issuedAt,
    DateTime? expiresAt,
  }) async {
    var detail = await readDetail(assetId);
    if (detail == null || _string(_map(detail.payload['links'])['add_version']) == null) {
      await refreshDetail(assetId);
      detail = await readDetail(assetId);
    }
    final path = _string(_map(detail?.payload['links'])['add_version']);
    if (path == null) {
      throw StateError('New version is not available for this document.');
    }
    final id = await addDocumentVersion(
      path: path,
      filePath: filePath,
      filename: filename,
      contentType: contentType,
      issuedAt: issuedAt,
      expiresAt: expiresAt,
    );
    try {
      await refreshDetail(assetId);
    } on Object {
      // The owner mutation is already confirmed; refresh is best-effort.
    }
    return id;
  }

  Future<String> createDocument({
    required String title,
    required String kind,
    required String sensitivity,
    required String filePath,
    required String filename,
    required String contentType,
    DateTime? issuedAt,
    DateTime? expiresAt,
  }) async {
    final client = api;
    if (client == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }

    var collection = await readCollectionPage(query: '', offset: 0);
    var createPath = _string(
      _map(_map(collection?.payload['documents'])['links'])['create'],
    );
    if (createPath == null && sync != null) {
      await refreshCollectionPage(query: '', offset: 0);
      collection = await readCollectionPage(query: '', offset: 0);
      createPath = _string(
        _map(_map(collection?.payload['documents'])['links'])['create'],
      );
    }
    if (createPath == null) {
      throw StateError('Document creation is not available.');
    }

    final response = await client.upload(
      _createMutationPath(createPath),
      fields: {
        'title': title.trim(),
        'kind': kind,
        'sensitivity': sensitivity,
        if (issuedAt != null) 'issued_at': _date(issuedAt),
        if (expiresAt != null) 'expires_at': _date(expiresAt),
      },
      files: [
        MakoloUploadFile(
          fieldName: 'file',
          path: filePath,
          filename: filename,
          contentType: contentType,
        ),
      ],
    );
    return _assetId(response);
  }

  Future<String> addDocumentVersion({
    required String path,
    required String filePath,
    required String filename,
    required String contentType,
    DateTime? issuedAt,
    DateTime? expiresAt,
  }) async {
    final client = api;
    if (client == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    final response = await client.upload(
      _assetMutationPath(path, action: 'versions'),
      fields: {
        if (issuedAt != null) 'issued_at': _date(issuedAt),
        if (expiresAt != null) 'expires_at': _date(expiresAt),
      },
      files: [
        MakoloUploadFile(
          fieldName: 'file',
          path: filePath,
          filename: filename,
          contentType: contentType,
        ),
      ],
    );
    return _assetId(response);
  }

  Future<void> archiveDocument({required String path}) async {
    final client = api;
    if (client == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    await client.post(_assetMutationPath(path, action: 'archive'));
  }

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

  Future<String> downloadVersionForReader({
    required String path,
    required String assetId,
    required String title,
    required int versionNumber,
    required String extension,
    required bool textPreview,
    TransferProgress? onProgress,
  }) async {
    if (sync?.isActive == false ||
        (await readDetailSource(assetId)).invalidated) {
      throw StateError('Resource owner permission withdrawn');
    }
    final client = api;
    if (client == null) {
      throw StateError('Remote PersonalAsset owner is not configured.');
    }
    final staging = await ProfilePaths.stagingFiles(profileId);
    final directory = Directory(
      p.join(
        staging.path,
        'resource-reader-${ProfilePaths.safeProfileId(assetId)}-'
        '${DateTime.now().toUtc().microsecondsSinceEpoch}',
      ),
    );
    await directory.create(recursive: true);
    final safeExtension = extension.replaceAll(RegExp(r'[^a-zA-Z0-9]'), '');
    final fileName = _safeExportName(
      '${title.trim().isEmpty ? 'Document' : title}-v$versionNumber',
      textPreview ? 'txt' : safeExtension,
    );
    final destination = p.join(directory.path, fileName);
    try {
      final ownerPath = _versionActionPath(path, action: 'download');
      await client.download(
        textPreview ? '$ownerPath?view=text' : ownerPath,
        destinationPath: destination,
        onProgress: onProgress,
      );
      if (sync?.isActive == false ||
          (await readDetailSource(assetId)).invalidated) {
        if (await directory.exists()) await directory.delete(recursive: true);
        throw StateError('Resource owner permission withdrawn during transfer');
      }
      return destination;
    } on Object {
      if (await directory.exists()) await directory.delete(recursive: true);
      rethrow;
    }
  }

  Future<String> downloadVersionForExplicitExport({
    required String path,
    required String assetId,
    required String title,
    required int versionNumber,
    required bool retainOfflineCopy,
    String? fileExtension,
    TransferProgress? onProgress,
  }) async {
    if (retainOfflineCopy) {
      await downloadVersionToLocal(
        path: path,
        assetId: assetId,
        title: title,
        versionNumber: versionNumber,
        onProgress: onProgress,
      );
      return resourceDownloadDestination(
        profileId: profileId,
        assetId: assetId,
        title: title,
        versionNumber: versionNumber,
      );
    }

    if (sync?.isActive == false ||
        (await readDetailSource(assetId)).invalidated) {
      throw StateError('Resource owner permission withdrawn');
    }
    final staging = await ProfilePaths.stagingFiles(profileId);
    final directory = Directory(
      p.join(
        staging.path,
        'resource-export-${ProfilePaths.safeProfileId(assetId)}-'
        '${DateTime.now().toUtc().microsecondsSinceEpoch}',
      ),
    );
    await directory.create(recursive: true);
    final destination = p.join(
      directory.path,
      _safeExportName(
        '${title.trim().isEmpty ? 'Document' : title}-v$versionNumber',
        fileExtension ?? 'bin',
      ),
    );
    try {
      await downloadVersion(
        path: path,
        destinationPath: destination,
        onProgress: onProgress,
      );
      if (sync?.isActive == false ||
          (await readDetailSource(assetId)).invalidated) {
        final withdrawn = File(destination);
        if (await withdrawn.exists()) await withdrawn.delete();
        throw StateError('Resource owner permission withdrawn during transfer');
      }
      return destination;
    } on Object {
      final partial = File(destination);
      if (await partial.exists()) await partial.delete();
      final parent = partial.parent;
      if (await parent.exists()) {
        try {
          await parent.delete();
        } on FileSystemException {
          // Best-effort staging cleanup.
        }
      }
      rethrow;
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
      _versionActionPath(path, action: 'download'),
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
      _versionActionPath(path, action: 'reuse'),
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

  String _versionActionPath(String path, {required String action}) {
    final relative = _sameOriginRelative(path);
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

  String _createMutationPath(String path) {
    final relative = _sameOriginRelative(path);
    if (relative != 'api/v1/me/resources/create/') {
      throw const FormatException('PersonalAsset create path mismatch');
    }
    return relative;
  }

  String _assetMutationPath(String path, {required String action}) {
    final relative = _sameOriginRelative(path);
    final ownerRoute = RegExp(
      r'^api/v1/me/resources/'
      r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
      r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/(versions|archive)/$',
    );
    if (!ownerRoute.hasMatch(relative) || !relative.endsWith('/$action/')) {
      throw const FormatException('PersonalAsset mutation path mismatch');
    }
    return relative;
  }

  String _sameOriginRelative(String path) {
    final uri = Uri.tryParse(path);
    if (uri == null ||
        uri.hasScheme ||
        uri.hasAuthority ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw const FormatException('Unexpected PersonalAsset owner link');
    }
    return uri.path.startsWith('/') ? uri.path.substring(1) : uri.path;
  }

  String _assetId(ApiResponse response) {
    final envelope = response.jsonObject();
    final data = _map(envelope['data']);
    final id = _string(data['id']);
    if (id == null) {
      throw const FormatException('Invalid PersonalAsset mutation response.');
    }
    return id;
  }

  String _date(DateTime value) {
    final month = value.month.toString().padLeft(2, '0');
    final day = value.day.toString().padLeft(2, '0');
    return '${value.year}-$month-$day';
  }
}

String _safeExportName(String stem, String extension) {
  final safeStem = stem
      .replaceAll(RegExp(r'[\\/:*?"<>|\x00-\x1f]+'), '-')
      .replaceAll(RegExp(r'\s+'), ' ')
      .replaceAll(RegExp(r'^[. ]+|[. ]+
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

List<ResourceOption> _options(Object? value) {
  if (value is! List) return const [];
  final options = <ResourceOption>[];
  for (final raw in value) {
    final row = _map(raw);
    final id = _string(row['id']);
    final label = _string(row['label']);
    if (id != null && label != null) {
      options.add(ResourceOption(id: id, label: label));
    }
  }
  return options;
}
), '')
      .trim();
  final bounded = safeStem.isEmpty
      ? 'Document Makolo'
      : safeStem.length > 90
      ? safeStem.substring(0, 90).trimRight()
      : safeStem;
  final cleanExtension = extension.toLowerCase().replaceAll(
    RegExp(r'[^a-z0-9]'),
    '',
  );
  return '$bounded.${cleanExtension.isEmpty ? 'bin' : cleanExtension}';
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

List<ResourceOption> _options(Object? value) {
  if (value is! List) return const [];
  final options = <ResourceOption>[];
  for (final raw in value) {
    final row = _map(raw);
    final id = _string(row['id']);
    final label = _string(row['label']);
    if (id != null && label != null) {
      options.add(ResourceOption(id: id, label: label));
    }
  }
  return options;
}
