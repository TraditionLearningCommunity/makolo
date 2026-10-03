import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';
import 'mps_models.dart';

class MpsPresentationRepository {
  MpsPresentationRepository({required this.store, required this.profileId, this.sync});

  static const artifactFreshness = FreshnessPolicy(id: 'mps-artifact', refreshRecommendedAfter: Duration(hours: 6));
  static const immutableDefinitionFreshness = FreshnessPolicy(id: 'mps-immutable-definition');

  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  String accessArtifactKey(String accessId) => 'access:$accessId:access_pass';

  String activityArtifactKey(String activityId, String purpose) =>
      'activity:$activityId:$purpose';

  SyncSourceDefinition accessArtifactSource(String accessId) => SyncSourceDefinition.projectionEnvelope(
    sourceKey: 'mps:access:$accessId:access_pass',
    owner: 'Presentation',
    path: 'api/v1/presentations/accesses/$accessId/',
    projectionKind: mpsArtifactProjectionKind,
    resourceKey: accessArtifactKey(accessId),
    category: SyncSourceCategory.keyedDetail,
    freshnessPolicy: artifactFreshness,
  );

  SyncSourceDefinition activityArtifactSource(
    String activityId,
    String purpose,
  ) => SyncSourceDefinition.projectionEnvelope(
    sourceKey: 'mps:activity:$activityId:$purpose',
    owner: 'Presentation',
    path: 'api/v1/presentations/activities/$activityId/$purpose/',
    projectionKind: mpsArtifactProjectionKind,
    resourceKey: activityArtifactKey(activityId, purpose),
    category: SyncSourceCategory.keyedDetail,
    freshnessPolicy: artifactFreshness,
  );

  Stream<StoredProjection?> watchAccessArtifact(String accessId) =>
      store.watchProjection(mpsArtifactProjectionKind, resourceKey: accessArtifactKey(accessId));

  Future<MpsPresentationPackage?> readAccessPackage(String accessId) async {
    final projection = await store.readProjection(mpsArtifactProjectionKind, resourceKey: accessArtifactKey(accessId));
    if (projection == null) return null;
    return _packageFor(MpsArtifact.fromProjection(projection));
  }

  Future<MpsPresentationPackage?> readActivityPackage(
    String activityId,
    String purpose,
  ) async {
    final projection = await store.readProjection(
      mpsArtifactProjectionKind,
      resourceKey: activityArtifactKey(activityId, purpose),
    );
    if (projection == null) return null;
    return _packageFor(MpsArtifact.fromProjection(projection));
  }

  Future<void> refreshActivity(String activityId, String purpose) =>
      _refreshArtifact(activityArtifactSource(activityId, purpose));

  Future<void> refreshAccess(String accessId) =>
      _refreshArtifact(accessArtifactSource(accessId));

  Future<void> _refreshArtifact(SyncSourceDefinition source) async {
    final engine = sync;
    if (engine == null) throw StateError('Remote Presentation owner is not configured.');
    await engine.refreshSource(source);
    final projection = await store.readProjection(
      mpsArtifactProjectionKind,
      resourceKey: source.resourceKey,
    );
    if (projection == null) return;
    final artifact = MpsArtifact.fromProjection(projection);
    await _ensureDefinition(artifact.template, projectionKind: mpsTemplateProjectionKind);
    await _ensureDefinition(artifact.theme, projectionKind: mpsThemeProjectionKind);
  }

  Future<MpsPresentationPackage> _packageFor(MpsArtifact artifact) async {
    var fallback = false;
    Map<String, dynamic> manifest = mpsEssentialManifest;
    if (!artifact.template.builtin) {
      final projection = await store.readProjection(mpsTemplateProjectionKind, resourceKey: artifact.template.resourceKey);
      final candidate = projection == null ? const <String,dynamic>{} : mpsMap(projection.payload['manifest']);
      if (candidate.isNotEmpty) {
        manifest = candidate;
      } else {
        fallback = true;
      }
    }

    Map<String, dynamic> theme = mpsEssentialTheme;
    if (!artifact.theme.builtin) {
      final projection = await store.readProjection(mpsThemeProjectionKind, resourceKey: artifact.theme.resourceKey);
      final candidate = projection == null ? const <String,dynamic>{} : mpsMap(projection.payload['tokens']);
      if (candidate.isNotEmpty) {
        theme = candidate;
      } else {
        fallback = true;
      }
    }

    return MpsPresentationPackage(artifact: artifact, manifest: manifest, themeTokens: theme, usedFallback: fallback);
  }

  Future<void> _ensureDefinition(MpsDefinitionRef definition, {required String projectionKind}) async {
    if (definition.builtin) return;
    if (await store.readProjection(projectionKind, resourceKey: definition.resourceKey) != null) return;
    final path = definition.path;
    final engine = sync;
    if (path == null || engine == null) return;
    await engine.refreshSource(SyncSourceDefinition.projectionEnvelope(
      sourceKey: '$projectionKind:${definition.resourceKey}',
      owner: 'Presentation',
      path: path,
      projectionKind: projectionKind,
      resourceKey: definition.resourceKey,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: immutableDefinitionFreshness,
    ));
  }
}
