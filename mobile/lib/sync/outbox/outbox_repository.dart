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

  Stream<List<OutboxOperation>> watchResource({
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
    return query.watch();
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

  Future<void> beginAttempt(String operationId) async {
    final row =
        await (database.select(database.outboxOperations)..where(
              (candidate) =>
                  candidate.profileId.equals(profileId) &
                  candidate.operationId.equals(operationId),
            ))
            .getSingle();
    await (database.update(database.outboxOperations)..where(
          (candidate) =>
              candidate.profileId.equals(profileId) &
              candidate.operationId.equals(operationId),
        ))
        .write(
          OutboxOperationsCompanion(
            state: Value(OutboxState.inFlight.wireValue),
            attempts: Value(row.attempts + 1),
            lastErrorCode: const Value(null),
          ),
        );
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
