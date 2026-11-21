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

  // The authenticated Profile owns the local database, but a Space
  // presentation has its own read snapshot and source status. Never reuse a
  // Dossier cached under another active Space.
  static String contextQuery(String? spaceSlug) => spaceSlug == null
      ? ''
      : '?context=space&space=${Uri.encodeQueryComponent(spaceSlug)}';

  static String detailResourceKey(String id, {String? spaceSlug}) =>
      spaceSlug == null ? id : '$id:space:$spaceSlug';

  String sourceKey(ObjectiveDepth kind, String id, {String? spaceSlug}) {
    final prefix = kind == ObjectiveDepth.dossier ? 'dossier' : 'project';
    return '$prefix:${detailResourceKey(id, spaceSlug: spaceSlug)}';
  }

  SyncSourceDefinition sourceFor(
    ObjectiveDepth kind,
    String id, {
    String? spaceSlug,
  }) {
    final segment = kind == ObjectiveDepth.dossier ? 'dossiers' : 'projects';
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: sourceKey(kind, id, spaceSlug: spaceSlug),
      owner: 'Objectives',
      path: 'api/v1/objectives/$segment/$id/${contextQuery(spaceSlug)}',
      projectionKind: projectionKind(kind),
      resourceKey: detailResourceKey(id, spaceSlug: spaceSlug),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<StoredProjection?> watch(
    ObjectiveDepth kind,
    String id, {
    String? spaceSlug,
  }) => store.watchProjection(
    projectionKind(kind),
    resourceKey: detailResourceKey(id, spaceSlug: spaceSlug),
  );

  Future<StoredProjection?> read(
    ObjectiveDepth kind,
    String id, {
    String? spaceSlug,
  }) => store.readProjection(
    projectionKind(kind),
    resourceKey: detailResourceKey(id, spaceSlug: spaceSlug),
  );

  Stream<OwnerSourceState> watchSource(
    ObjectiveDepth kind,
    String id, {
    String? spaceSlug,
  }) => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: sourceKey(kind, id, spaceSlug: spaceSlug),
  );

  Future<OwnerSourceState> readSource(
    ObjectiveDepth kind,
    String id, {
    String? spaceSlug,
  }) => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: sourceKey(kind, id, spaceSlug: spaceSlug),
  );

  // One owner-scoped three-kind window shared by Cartes, Liste and Explorateur.
  // Separate from the historic shallow Project/Dossier collection sources.
  static const organizerLimit = 50;
  static const organizerProjectionKind = 'objective.organizer.collection';

  static String organizerStorageKey(int offset, {String? spaceSlug}) =>
      spaceSlug == null
      ? 'offset:$offset:limit:$organizerLimit'
      : 'space:$spaceSlug:offset:$offset:limit:$organizerLimit';

  String organizerResourceKey(int offset, {String? spaceSlug}) =>
      organizerStorageKey(offset, spaceSlug: spaceSlug);

  String organizerSourceKey(int offset, {String? spaceSlug}) =>
      '$organizerProjectionKind:${organizerStorageKey(offset, spaceSlug: spaceSlug)}';

  SyncSourceDefinition organizerSourceFor(
    int offset, {
    String? spaceSlug,
  }) => SyncSourceDefinition.projectionEnvelope(
    sourceKey: organizerSourceKey(offset, spaceSlug: spaceSlug),
    owner: 'Objectives',
    path:
        'api/v1/objectives/organizer/?limit=$organizerLimit&offset=$offset'
        '${spaceSlug == null ? '' : '&context=space&space=${Uri.encodeQueryComponent(spaceSlug)}'}',
    projectionKind: organizerProjectionKind,
    resourceKey: organizerResourceKey(offset, spaceSlug: spaceSlug),
    category: SyncSourceCategory.collection,
    freshnessPolicy: freshnessPolicy,
  );

  Stream<List<StoredProjection>> watchOrganizer() =>
      store.watchProjections(organizerProjectionKind);

  Future<StoredProjection?> readOrganizerPage(
    int offset, {
    String? spaceSlug,
  }) => store.readProjection(
    organizerProjectionKind,
    resourceKey: organizerResourceKey(offset, spaceSlug: spaceSlug),
  );

  Stream<OwnerSourceState> watchOrganizerSource({String? spaceSlug}) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: organizerSourceKey(0, spaceSlug: spaceSlug),
      );

  Future<OwnerSourceState> readOrganizerSource({String? spaceSlug}) =>
      readOrganizerSourceForOffset(0, spaceSlug: spaceSlug);

  /// A continuation has its own owner status and the selected Space lens.
  Future<OwnerSourceState> readOrganizerSourceForOffset(
    int offset, {
    String? spaceSlug,
  }) => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: organizerSourceKey(offset, spaceSlug: spaceSlug),
  );

  Future<void> refreshOrganizerPage(int offset, {String? spaceSlug}) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Objectives owner is not configured.');
    }
    await engine.refreshSource(
      organizerSourceFor(offset, spaceSlug: spaceSlug),
    );
  }

  static const projectDossierProjectionKind =
      'objective.project.dossiers.collection';
  static const projectDossierLimit = 50;

  static String projectDossierStorageKey(
    String projectId,
    int offset, {
    String? spaceSlug,
  }) => spaceSlug == null
      ? '$projectId:$offset:$projectDossierLimit'
      : '$projectId:space:$spaceSlug:$offset:$projectDossierLimit';

  String projectDossierResourceKey(
    String projectId,
    int offset, {
    String? spaceSlug,
  }) => projectDossierStorageKey(projectId, offset, spaceSlug: spaceSlug);

  SyncSourceDefinition projectDossierSource(
    String projectId,
    int offset, {
    String? spaceSlug,
  }) => SyncSourceDefinition.projectionEnvelope(
    sourceKey:
        'project:dossiers:${projectDossierStorageKey(projectId, offset, spaceSlug: spaceSlug)}',
    owner: 'Objectives',
    path:
        'api/v1/objectives/projects/$projectId/dossiers/'
        '?limit=$projectDossierLimit&offset=$offset'
        '${spaceSlug == null ? '' : '&context=space&space=${Uri.encodeQueryComponent(spaceSlug)}'}',
    projectionKind: projectDossierProjectionKind,
    resourceKey: projectDossierResourceKey(
      projectId,
      offset,
      spaceSlug: spaceSlug,
    ),
    category: SyncSourceCategory.collection,
    freshnessPolicy: freshnessPolicy,
  );

  Stream<List<StoredProjection>> watchProjectDossiers() =>
      store.watchProjections(projectDossierProjectionKind);

  Future<void> refreshProjectDossiers(
    String projectId,
    int offset, {
    String? spaceSlug,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Objectives synchronization unavailable.');
    }
    await engine.refreshSource(
      projectDossierSource(projectId, offset, spaceSlug: spaceSlug),
    );
  }

  static const collectionLimit = 24;

  String collectionKind(ObjectiveDepth kind) => switch (kind) {
    ObjectiveDepth.dossier => 'objective.dossier.collection',
    ObjectiveDepth.project => 'objective.project.collection',
  };

  String collectionResourceKey(int offset) =>
      'offset:$offset:limit:$collectionLimit';

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
      path: 'api/v1/objectives/$segment/?limit=$collectionLimit&offset=$offset',
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

  Future<void> refresh(
    ObjectiveDepth kind,
    String id, {
    String? spaceSlug,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Objectives owner is not configured.');
    }
    await engine.refreshSource(sourceFor(kind, id, spaceSlug: spaceSlug));
  }
}
