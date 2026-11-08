import 'package:drift/drift.dart';

import '../../app/runtime/actor_context.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class SpaceOccurrenceSourceState {
  const SpaceOccurrenceSourceState({
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

  static const unknown = SpaceOccurrenceSourceState();
}

class SpaceOccurrenceRepository {
  SpaceOccurrenceRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const dayOfProjection = 'space.occurrence.day_of';
  static const liveProjection = 'space.occurrence.live';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'space-operational-volatile',
    refreshRecommendedAfter: Duration(seconds: 30),
    usableButOldAfter: Duration(minutes: 2),
    revalidateAfterFreshUntil: true,
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  String resourceKey(SpaceActorIdentity space, String occurrenceId) =>
      '${space.id}|$occurrenceId';

  SyncSourceDefinition dayOfSource(
    SpaceActorIdentity space,
    String occurrenceId,
  ) => SyncSourceDefinition.projectionEnvelope(
    sourceKey: 'space-day-of:${space.id}:$occurrenceId',
    owner: 'Operations',
    path: 'api/v1/operations/occurrences/$occurrenceId/day-of/',
    projectionKind: dayOfProjection,
    resourceKey: resourceKey(space, occurrenceId),
    actorScope: SyncActorScope.space(spaceId: space.id),
    category: SyncSourceCategory.boundedOperational,
    freshnessPolicy: freshnessPolicy,
  );

  SyncSourceDefinition liveSource(
    SpaceActorIdentity space,
    String occurrenceId,
  ) => SyncSourceDefinition(
    sourceKey: 'space-live:${space.id}:$occurrenceId',
    owner: 'Operations',
    path: 'api/v1/operations/occurrences/$occurrenceId/live/',
    projectionKind: liveProjection,
    resourceKey: resourceKey(space, occurrenceId),
    actorScope: SyncActorScope.space(spaceId: space.id),
    category: SyncSourceCategory.boundedOperational,
    freshnessPolicy: freshnessPolicy,
    parser: (response) =>
        AcquiredProjection(schemaVersion: 1, payload: response.jsonObject()),
    applier: applyProjectionSnapshot,
  );

  Stream<StoredProjection?> watchDayOf(
    SpaceActorIdentity space,
    String occurrenceId,
  ) => store.watchProjection(
    dayOfProjection,
    resourceKey: resourceKey(space, occurrenceId),
  );

  Stream<StoredProjection?> watchLive(
    SpaceActorIdentity space,
    String occurrenceId,
  ) => store.watchProjection(
    liveProjection,
    resourceKey: resourceKey(space, occurrenceId),
  );

  Stream<SpaceOccurrenceSourceState> watchSource(SyncSourceDefinition source) {
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(source.sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? SpaceOccurrenceSourceState.unknown
          : SpaceOccurrenceSourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<void> refreshDayOf(
    SpaceActorIdentity space,
    String occurrenceId,
  ) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Operations owner is not configured.');
    }
    await engine.refreshSource(dayOfSource(space, occurrenceId));
  }

  Future<void> refreshLive(
    SpaceActorIdentity space,
    String occurrenceId,
  ) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Operations owner is not configured.');
    }
    await engine.refreshSource(liveSource(space, occurrenceId));
  }
}
