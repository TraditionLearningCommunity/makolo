import '../../app/runtime/actor_context.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

/// Retained metadata only. Private file bytes remain on the Journey owner and
/// are downloaded into a disposable, Profile-scoped reader when requested.
class JourneyArtifactRepository {
  const JourneyArtifactRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'journey.artifacts';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'journey-artifacts-private',
    refreshRecommendedAfter: Duration(minutes: 10),
    usableButOldAfter: Duration(hours: 2),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  static String resourceKey(String journeyId, {SpaceActorIdentity? space}) =>
      space == null ? 'profile:$journeyId' : 'space:${space.id}:$journeyId';

  static String path(String journeyId, {SpaceActorIdentity? space}) =>
      space == null
      ? 'api/v1/me/journeys/$journeyId/artifacts/'
      : 'api/v1/organizations/workspaces/${Uri.encodeComponent(space.slug)}/beneficiary/journeys/$journeyId/artifacts/';

  SyncSourceDefinition sourceFor(
    String journeyId, {
    SpaceActorIdentity? space,
  }) {
    final key = resourceKey(journeyId, space: space);
    return SyncSourceDefinition(
      sourceKey: 'journey-artifacts:$key',
      owner: 'Journeys',
      path: path(journeyId, space: space),
      projectionKind: projectionKind,
      resourceKey: key,
      actorScope: space == null
          ? const SyncActorScope.personal()
          : SyncActorScope.space(spaceId: space.id),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
      parser: (response) {
        final payload = response.jsonObject();
        final owner = payload['owner'];
        final beneficiary = payload['beneficiary'];
        if (owner is! Map ||
            owner['kind'] != 'journey' ||
            owner['id'] != journeyId ||
            beneficiary is! Map ||
            beneficiary['kind'] != (space == null ? 'profile' : 'space') ||
            beneficiary['id'] != (space?.id ?? profileId) ||
            payload['artifacts'] is! List) {
          throw const FormatException('Unexpected private JourneyArtifact owner');
        }
        return AcquiredProjection(schemaVersion: 1, payload: payload);
      },
      applier: applyProjectionSnapshot,
    );
  }

  Stream<StoredProjection?> watch(
    String journeyId, {
    SpaceActorIdentity? space,
  }) => store.watchProjection(
    projectionKind,
    resourceKey: resourceKey(journeyId, space: space),
  );

  Future<StoredProjection?> read(
    String journeyId, {
    SpaceActorIdentity? space,
  }) => store.readProjection(
    projectionKind,
    resourceKey: resourceKey(journeyId, space: space),
  );

  Stream<OwnerSourceState> watchSource(
    String journeyId, {
    SpaceActorIdentity? space,
  }) => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: sourceFor(journeyId, space: space).sourceKey,
  );

  Future<void> refresh(
    String journeyId, {
    SpaceActorIdentity? space,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Journey owner sync is not available.');
    }
    await engine.refreshSource(sourceFor(journeyId, space: space));
  }
}

class SpaceBeneficiaryJourneyRepository {
  const SpaceBeneficiaryJourneyRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'space.service.journey.detail';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'space-beneficiary-journey',
    refreshRecommendedAfter: Duration(minutes: 15),
    usableButOldAfter: Duration(hours: 2),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  static String resourceKey(SpaceActorIdentity space, String journeyId) =>
      '${space.id}:$journeyId';

  SyncSourceDefinition sourceFor(SpaceActorIdentity space, String journeyId) {
    return SyncSourceDefinition(
      sourceKey: 'space-beneficiary-journey:${resourceKey(space, journeyId)}',
      owner: 'Services',
      path: 'api/v1/organizations/workspaces/${Uri.encodeComponent(space.slug)}/beneficiary/journeys/$journeyId/',
      projectionKind: projectionKind,
      resourceKey: resourceKey(space, journeyId),
      actorScope: SyncActorScope.space(spaceId: space.id),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
      parser: (response) {
        final envelope = response.jsonObject();
        final meta = envelope['meta'];
        final payload = envelope['data'];
        final identity = payload is Map ? payload['identity'] : null;
        final beneficiary = identity is Map ? identity['beneficiary'] : null;
        final selected = payload is Map ? payload['space'] : null;
        if (meta is! Map ||
            meta['projection'] != projectionKind ||
            meta['schema_version'] != 1 ||
            payload is! Map<String, dynamic> ||
            identity is! Map ||
            identity['kind'] != 'journey' ||
            identity['id'] != journeyId ||
            beneficiary is! Map ||
            beneficiary['kind'] != 'space' ||
            beneficiary['id'] != space.id ||
            selected is! Map ||
            selected['id'] != space.id ||
            selected['slug'] != space.slug) {
          throw const FormatException('Unexpected Space beneficiary Journey owner');
        }
        return AcquiredProjection(schemaVersion: 1, payload: payload);
      },
      applier: applyProjectionSnapshot,
    );
  }

  Stream<StoredProjection?> watch(SpaceActorIdentity space, String journeyId) =>
      store.watchProjection(
        projectionKind,
        resourceKey: resourceKey(space, journeyId),
      );

  Stream<OwnerSourceState> watchSource(
    SpaceActorIdentity space,
    String journeyId,
  ) => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: sourceFor(space, journeyId).sourceKey,
  );

  Future<void> refresh(SpaceActorIdentity space, String journeyId) async {
    final engine = sync;
    if (engine == null) throw StateError('Space Journey sync is not available.');
    await engine.refreshSource(sourceFor(space, journeyId));
  }
}
