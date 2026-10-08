import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class LiveSourceState {
  const LiveSourceState({
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

  static const unknown = LiveSourceState();
}

class LiveRepository {
  LiveRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'personal.occurrence.live';
  static const freshnessPolicy = FreshnessPolicy(
    id: 'live-volatile',
    refreshRecommendedAfter: Duration(seconds: 30),
    usableButOldAfter: Duration(minutes: 2),
    revalidateAfterFreshUntil: true,
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor(String occurrenceId) =>
      SyncSourceDefinition.projectionEnvelope(
        sourceKey: 'live:$occurrenceId',
        owner: 'Operations',
        path: 'api/v1/me/occurrences/$occurrenceId/live/',
        projectionKind: projectionKind,
        resourceKey: occurrenceId,
        category: SyncSourceCategory.boundedOperational,
        freshnessPolicy: freshnessPolicy,
      );

  Stream<StoredProjection?> watch(String occurrenceId) =>
      store.watchProjection(projectionKind, resourceKey: occurrenceId);

  Stream<LiveSourceState> watchSource(String occurrenceId) {
    final sourceKey = sourceFor(occurrenceId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? LiveSourceState.unknown
          : LiveSourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<void> refresh(String occurrenceId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Operations owner is not configured.');
    }
    await engine.refreshSource(sourceFor(occurrenceId));
  }
}
