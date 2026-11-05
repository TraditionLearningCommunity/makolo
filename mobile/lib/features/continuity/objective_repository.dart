import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

enum ObjectiveDepth { dossier, project }

class ObjectiveRepository {
  ObjectiveRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const dossierProjectionKind = 'objective.dossier.detail';
  static const projectProjectionKind = 'objective.project.detail';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'objective-contextual',
    refreshRecommendedAfter: Duration(hours: 2),
    usableButOldAfter: Duration(days: 2),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  String projectionKind(ObjectiveDepth kind) => switch (kind) {
    ObjectiveDepth.dossier => dossierProjectionKind,
    ObjectiveDepth.project => projectProjectionKind,
  };

  String sourceKey(ObjectiveDepth kind, String id) {
    final prefix = kind == ObjectiveDepth.dossier ? 'dossier' : 'project';
    return '$prefix:$id';
  }

  SyncSourceDefinition sourceFor(ObjectiveDepth kind, String id) {
    final segment = kind == ObjectiveDepth.dossier ? 'dossiers' : 'projects';
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: sourceKey(kind, id),
      owner: 'Objectives',
      path: 'api/v1/objectives/$segment/$id/',
      projectionKind: projectionKind(kind),
      resourceKey: id,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<StoredProjection?> watch(ObjectiveDepth kind, String id) =>
      store.watchProjection(projectionKind(kind), resourceKey: id);

  Future<StoredProjection?> read(ObjectiveDepth kind, String id) =>
      store.readProjection(projectionKind(kind), resourceKey: id);

  Stream<OwnerSourceState> watchSource(ObjectiveDepth kind, String id) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: sourceKey(kind, id),
      );

  Future<OwnerSourceState> readSource(ObjectiveDepth kind, String id) =>
      readOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: sourceKey(kind, id),
      );

  static const collectionLimit = 24;

  String collectionKind(ObjectiveDepth kind) => switch (kind) {
    ObjectiveDepth.dossier => 'objective.dossier.collection',
    ObjectiveDepth.project => 'objective.project.collection',
  };

  String collectionResourceKey(int offset) => 'offset:$offset:limit:$collectionLimit';

  String collectionSourceKey(ObjectiveDepth kind, int offset) =>
      '${collectionKind(kind)}:$offset:$collectionLimit';

  SyncSourceDefinition collectionSourceFor(
    ObjectiveDepth kind, {
    required int offset,
  }) {
    final segment = kind == ObjectiveDepth.dossier ? 'dossiers' : 'projects';
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: collectionSourceKey(kind, offset),
      owner: 'Objectives',
      path:
          'api/v1/objectives/$segment/?limit=$collectionLimit&offset=$offset',
      projectionKind: collectionKind(kind),
      resourceKey: collectionResourceKey(offset),
      category: SyncSourceCategory.collection,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<List<StoredProjection>> watchCollection(ObjectiveDepth kind) =>
      store.watchProjections(collectionKind(kind));

  Future<StoredProjection?> readCollectionPage(
    ObjectiveDepth kind, {
    required int offset,
  }) => store.readProjection(
    collectionKind(kind),
    resourceKey: collectionResourceKey(offset),
  );

  Future<OwnerSourceState> readCollectionSource(
    ObjectiveDepth kind, {
    required int offset,
  }) => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: collectionSourceKey(kind, offset),
  );

  Stream<OwnerSourceState> watchCollectionSource(ObjectiveDepth kind) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: collectionSourceKey(kind, 0),
      );

  Future<void> refreshCollectionPage(
    ObjectiveDepth kind, {
    required int offset,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Objectives owner is not configured.');
    }
    await engine.refreshSource(collectionSourceFor(kind, offset: offset));
  }

  Future<void> refresh(ObjectiveDepth kind, String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Objectives owner is not configured.');
    }
    await engine.refreshSource(sourceFor(kind, id));
  }
}
