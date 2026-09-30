import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class DayOfSourceState {
  const DayOfSourceState({
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

  static const unknown = DayOfSourceState();
}

class DayOfRepository {
  DayOfRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'personal.occurrence.day_of';

  static const freshnessPolicy = FreshnessPolicy(id: 'day-of-volatile');

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor(String occurrenceId) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'day-of:$occurrenceId',
      owner: 'Operations',
      path: 'api/v1/me/occurrences/$occurrenceId/day-of/',
      projectionKind: projectionKind,
      resourceKey: occurrenceId,
      category: SyncSourceCategory.boundedOperational,
      freshnessPolicy: freshnessPolicy,
    );
  }

  Stream<StoredProjection?> watchDetail(String occurrenceId) {
    return store.watchProjection(projectionKind, resourceKey: occurrenceId);
  }

  Future<StoredProjection?> readDetail(String occurrenceId) {
    return store.readProjection(projectionKind, resourceKey: occurrenceId);
  }

  Stream<DayOfSourceState> watchSource(String occurrenceId) {
    final sourceKey = sourceFor(occurrenceId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? DayOfSourceState.unknown
          : DayOfSourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<DayOfSourceState> readSource(String occurrenceId) async {
    final sourceKey = sourceFor(occurrenceId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    final row = await query.getSingleOrNull();
    return row == null
        ? DayOfSourceState.unknown
        : DayOfSourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  Future<void> refreshDetail(String occurrenceId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Operations owner is not configured.');
    }
    await engine.refreshSource(sourceFor(occurrenceId));
  }

  Future<void> invalidateDetail(String occurrenceId) async {
    final engine = sync;
    if (engine == null) return;
    await engine.invalidate(sourceFor(occurrenceId));
  }
}
