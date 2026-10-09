import 'dart:convert';

import '../../data/local/makolo_database.dart';
import '../../data/files/file_download_coordinator.dart';
import '../../data/files/profile_file_store.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class RequirementRepository {
  RequirementRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'personal.journey.requirement.detail';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'requirement-contextual',
    refreshRecommendedAfter: Duration(hours: 1),
    usableButOldAfter: Duration(hours: 24),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor({
    required String journeyId,
    required String assessmentId,
    String? detailPath,
  }) {
    final path =
        detailPath ??
        '/api/v1/me/journeys/$journeyId/requirements/$assessmentId/';
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'requirement:$assessmentId',
      owner: 'Requirements',
      path: _relativeApiPath(path),
      projectionKind: projectionKind,
      resourceKey: assessmentId,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<StoredProjection?> watchDetail(String assessmentId) =>
      store.watchProjection(projectionKind, resourceKey: assessmentId);

  Future<StoredProjection?> readDetail(String assessmentId) =>
      store.readProjection(projectionKind, resourceKey: assessmentId);

  Stream<OwnerSourceState> watchSource(String assessmentId) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'requirement:$assessmentId',
      );

  Future<OwnerSourceState> readSource(String assessmentId) =>
      readOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'requirement:$assessmentId',
      );

  Future<void> refresh({
    required String journeyId,
    required String assessmentId,
    String? detailPath,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Requirements owner is not configured.');
    }
    await engine.refreshSource(
      sourceFor(
        journeyId: journeyId,
        assessmentId: assessmentId,
        detailPath: detailPath,
      ),
    );
  }
}

class PreparationResourcesRepository {
  PreparationResourcesRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.api,
    this.sync,
  });

  static const projectionKind = 'preparation.journey.resources';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'preparation-resources-contextual',
    refreshRecommendedAfter: Duration(hours: 1),
    usableButOldAfter: Duration(hours: 24),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final MakoloApiClient? api;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor({
    required String journeyId,
    String? resourcesPath,
  }) {
    final path =
        resourcesPath ?? '/api/v1/preparation/journeys/$journeyId/resources/';
    return SyncSourceDefinition(
      sourceKey: 'preparation-resources:$journeyId',
      owner: 'Preparation',
      path: _relativeApiPath(path),
      projectionKind: projectionKind,
      resourceKey: journeyId,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
      parser: (response) {
        final decoded = jsonDecode(response.body);
        if (decoded is! List) {
          throw const FormatException(
            'Expected Preparation owner resources list.',
          );
        }
        final items = decoded
            .map((value) {
              if (value is Map<String, dynamic>) return value;
              if (value is Map) {
                return value.map((key, item) => MapEntry(key.toString(), item));
              }
              throw const FormatException(
                'Expected Preparation resource object.',
              );
            })
            .toList(growable: false);
        return AcquiredProjection(schemaVersion: 1, payload: {'items': items});
      },
      applier: applyProjectionSnapshot,
    );
  }

  Stream<StoredProjection?> watchResources(String journeyId) =>
      store.watchProjection(projectionKind, resourceKey: journeyId);

  Future<StoredProjection?> readResources(String journeyId) =>
      store.readProjection(projectionKind, resourceKey: journeyId);

  Stream<OwnerSourceState> watchSource(String journeyId) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'preparation-resources:$journeyId',
      );

  Future<OwnerSourceState> readSource(String journeyId) => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'preparation-resources:$journeyId',
  );

  Future<void> refresh({
    required String journeyId,
    String? resourcesPath,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Preparation owner is not configured.');
    }
    await engine.refreshSource(
      sourceFor(journeyId: journeyId, resourcesPath: resourcesPath),
    );
  }

  Future<StoredLocalFile> downloadResource({
    required String resourceId,
    required String downloadPath,
    required String title,
    String? mimeType,
  }) async {
    final client = api;
    if (client == null) {
      throw StateError('Remote Preparation owner is not configured.');
    }
    final fileStore = await ProfileFileStore.open(
      database: database,
      profileId: profileId,
    );
    final coordinator = FileDownloadCoordinator(fileStore);
    return coordinator.download(
      fileId: 'preparation-resource:$resourceId',
      owner: 'Preparation',
      sourceFilename: _resourceFilename(
        resourceId: resourceId,
        title: title,
        mimeType: mimeType,
      ),
      purpose: 'journey_preparation',
      sensitivity: 'private',
      downloadTo: (destinationPath) async {
        await client.download(
          _relativeApiPath(downloadPath),
          destinationPath: destinationPath,
        );
      },
    );
  }
}

String _relativeApiPath(String value) {
  final trimmed = value.trim();
  if (trimmed.startsWith('/')) return trimmed.substring(1);
  return trimmed;
}

String _resourceFilename({
  required String resourceId,
  required String title,
  required String? mimeType,
}) {
  final extension = switch ((mimeType ?? '').toLowerCase()) {
    'application/pdf' => '.pdf',
    'image/jpeg' => '.jpg',
    'image/png' => '.png',
    'image/webp' => '.webp',
    'text/plain' => '.txt',
    _ => '',
  };
  final safeTitle = title
      .trim()
      .replaceAll(RegExp(r'[^A-Za-z0-9_-]+'), '_')
      .replaceAll(RegExp(r'_+'), '_');
  final stem = safeTitle.isEmpty ? resourceId : safeTitle;
  return '$stem$extension';
}
