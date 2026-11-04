import 'dart:convert';

import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';

enum OutboxState {
  queued('queued'),
  inFlight('in_flight'),
  awaitingConfirmation('awaiting_confirmation'),
  confirmed('confirmed'),
  conflict('conflict'),
  failed('failed'),
  cancelled('cancelled');

  const OutboxState(this.wireValue);
  final String wireValue;
}

enum ReplayPolicy {
  safe('safe'),
  idempotent('idempotent'),
  refetchBeforeRetry('refetch-before-retry'),
  noBlindRetry('no-blind-retry');

  const ReplayPolicy(this.wireValue);
  final String wireValue;

  bool get allowsAutomaticReplay =>
      this == ReplayPolicy.safe || this == ReplayPolicy.idempotent;

  bool get requiresOwnerIdempotency => this == ReplayPolicy.idempotent;

  bool get requiresReconciliationBeforeReplay =>
      this == ReplayPolicy.refetchBeforeRetry;

  bool get stopsOnAmbiguousResult => this == ReplayPolicy.noBlindRetry;
}

class OutboxResourceOperation {
  const OutboxResourceOperation({required this.state});

  final String state;
}

class OutboxSummary {
  const OutboxSummary({
    required this.pendingCount,
    required this.conflictCount,
    required this.failedCount,
  });

  final int pendingCount;
  final int conflictCount;
  final int failedCount;

  static const empty = OutboxSummary(
    pendingCount: 0,
    conflictCount: 0,
    failedCount: 0,
  );
}

class OutboxRepository {
  OutboxRepository(this.database, this.profileId);

  final MakoloDatabase database;
  final String profileId;

  Future<void> enqueue({
    required String operationId,
    required String deviceInstanceId,
    required String operationKind,
    required String owner,
    required Map<String, dynamic> payload,
    required String intentId,
    required ReplayPolicy replayPolicy,
    String? resourceKind,
    String? resourceId,
    String? ownerIdempotencyKey,
    List<String> dependencies = const [],
  }) {
    return database
        .into(database.outboxOperations)
        .insert(
          OutboxOperationsCompanion.insert(
            operationId: operationId,
            profileId: profileId,
            deviceInstanceId: deviceInstanceId,
            operationKind: operationKind,
            owner: owner,
            resourceKind: Value(resourceKind),
            resourceId: Value(resourceId),
            payloadJson: jsonEncode(payload),
            dependencyIdsJson: Value(jsonEncode(dependencies)),
            observedAt: DateTime.now().toUtc(),
            intentId: intentId,
            ownerIdempotencyKey: Value(ownerIdempotencyKey),
            replayPolicy: replayPolicy.wireValue,
          ),
        );
  }

  Future<List<OutboxOperation>> pending() async {
    final rows =
        await (database.select(database.outboxOperations)
              ..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.state.isIn([
                      OutboxState.queued.wireValue,
                      OutboxState.inFlight.wireValue,
                      OutboxState.failed.wireValue,
                      OutboxState.awaitingConfirmation.wireValue,
                    ]),
              )
              ..orderBy([(row) => OrderingTerm.asc(row.observedAt)]))
            .get();
    final now = DateTime.now().toUtc();
    return rows
        .where(
          (row) =>
              row.nextRetryAt == null || !row.nextRetryAt!.toUtc().isAfter(now),
        )
        .toList(growable: false);
  }

  Stream<List<OutboxResourceOperation>> watchResource({
    required String operationKind,
    required String resourceId,
  }) {
    final query = database.select(database.outboxOperations)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.operationKind.equals(operationKind) &
            row.resourceId.equals(resourceId),
      )
      ..orderBy([(row) => OrderingTerm.desc(row.observedAt)]);
    return query.watch().map(
      (rows) => rows
          .map((row) => OutboxResourceOperation(state: row.state))
          .toList(growable: false),
    );
  }

  Future<OutboxOperation?> activeForResource({
    required String operationKind,
    required String resourceId,
  }) async {
    final query = database.select(database.outboxOperations)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.operationKind.equals(operationKind) &
            row.resourceId.equals(resourceId) &
            row.state.isIn([
              OutboxState.queued.wireValue,
              OutboxState.inFlight.wireValue,
              OutboxState.awaitingConfirmation.wireValue,
            ]),
      )
      ..orderBy([(row) => OrderingTerm.desc(row.observedAt)])
      ..limit(1);
    return query.getSingleOrNull();
  }

  Stream<OutboxSummary> watchSummary() {
    final query = database.select(database.outboxOperations)
      ..where((row) => row.profileId.equals(profileId));
    return query.watch().map((rows) {
      var pendingCount = 0;
      var conflictCount = 0;
      var failedCount = 0;
      for (final row in rows) {
        if (row.state == OutboxState.conflict.wireValue) {
          conflictCount += 1;
        } else if (row.state == OutboxState.failed.wireValue) {
          failedCount += 1;
        } else if (row.state == OutboxState.queued.wireValue ||
            row.state == OutboxState.inFlight.wireValue ||
            row.state == OutboxState.awaitingConfirmation.wireValue) {
          pendingCount += 1;
        }
      }
      return OutboxSummary(
        pendingCount: pendingCount,
        conflictCount: conflictCount,
        failedCount: failedCount,
      );
    });
  }

  /// Profile-scoped atomic claim. A second processor must never dispatch
  /// the same operation while the first handler is still in flight.
  Future<bool> claimForAttempt(
    String operationId, {
    required int expectedAttempts,
    required String expectedState,
  }) async {
    if (expectedState != OutboxState.queued.wireValue &&
        expectedState != OutboxState.failed.wireValue &&
        expectedState != OutboxState.inFlight.wireValue &&
        expectedState != OutboxState.awaitingConfirmation.wireValue) {
      return false;
    }
    final changed = await (database.update(database.outboxOperations)..where(
          (candidate) =>
              candidate.profileId.equals(profileId) &
              candidate.operationId.equals(operationId) &
              candidate.state.equals(expectedState) &
              candidate.attempts.equals(expectedAttempts),
        ))
        .write(
          OutboxOperationsCompanion(
            state: Value(OutboxState.inFlight.wireValue),
            attempts: Value(expectedAttempts + 1),
            lastErrorCode: const Value(null),
          ),
        );
    return changed == 1;
  }

  /// Dependency statuses are read from this Profile exclusively. An unknown
  /// dependency never silently authorizes a mutation.
  Future<Map<String, String>> dependencyStates(
    Iterable<String> operationIds,
  ) async {
    final ids = operationIds.toSet();
    if (ids.isEmpty) return const {};
    final rows = await (database.select(database.outboxOperations)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.operationId.isIn(ids),
        ))
        .get();
    return {for (final row in rows) row.operationId: row.state};
  }

  /// Backward-compatible explicit start for existing callers.
  Future<void> beginAttempt(String operationId) async {
    final row = await (database.select(database.outboxOperations)..where(
      (candidate) => candidate.profileId.equals(profileId) &
          candidate.operationId.equals(operationId),
    )).getSingle();
    if (!await claimForAttempt(
      operationId,
      expectedAttempts: row.attempts,
      expectedState: row.state,
    )) throw StateError('Outbox operation already claimed');
  }

  Future<void> setState(
    String operationId,
    OutboxState state, {
    String? errorCode,
  }) async {
    await (database.update(database.outboxOperations)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.operationId.equals(operationId),
        ))
        .write(
          OutboxOperationsCompanion(
            state: Value(state.wireValue),
            lastErrorCode: Value(errorCode),
          ),
        );
  }
}
