import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class JourneySourceState {
  const JourneySourceState({
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

  static const unknown = JourneySourceState();
}

class JourneyRepository {
  JourneyRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'personal.journey.detail';

  static const freshnessPolicy = FreshnessPolicy(
    id: 'journey-contextual',
    refreshRecommendedAfter: Duration(hours: 1),
    usableButOldAfter: Duration(hours: 24),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor(String journeyId) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'journey:$journeyId',
      owner: 'Journeys',
      path: 'api/v1/me/journeys/$journeyId/',
      projectionKind: projectionKind,
      resourceKey: journeyId,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<StoredProjection?> watchDetail(String journeyId) {
    return store.watchProjection(projectionKind, resourceKey: journeyId);
  }

  Future<StoredProjection?> readDetail(String journeyId) {
    return store.readProjection(projectionKind, resourceKey: journeyId);
  }

  Stream<JourneySourceState> watchSource(String journeyId) {
    final sourceKey = sourceFor(journeyId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? JourneySourceState.unknown
          : JourneySourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<JourneySourceState> readSource(String journeyId) async {
    final sourceKey = sourceFor(journeyId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(sourceKey),
      );
    final row = await query.getSingleOrNull();
    return row == null
        ? JourneySourceState.unknown
        : JourneySourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  Future<void> refreshDetail(String journeyId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Journey owner is not configured.');
    }
    await engine.refreshSource(sourceFor(journeyId));
  }

  Future<void> invalidateDetail(String journeyId) async {
    final engine = sync;
    if (engine == null) return;
    await engine.invalidate(sourceFor(journeyId));
  }
}
