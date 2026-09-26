import 'dart:convert';

import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';

enum OutboxState {
  queued,
  inFlight,
  awaitingConfirmation,
  confirmed,
  conflict,
  failed,
  cancelled,
}

enum ReplayPolicy {
  safe,
  idempotent,
  refetchBeforeRetry,
  noBlindRetry,
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
    return database.into(database.outboxOperations).insert(
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
            replayPolicy: replayPolicy.name,
          ),
        );
  }

  Future<List<OutboxOperation>> pending() {
    return (database.select(database.outboxOperations)
          ..where(
            (row) =>
                row.profileId.equals(profileId) &
                row.state.isIn([
                  OutboxState.queued.name,
                  OutboxState.inFlight.name,
                  OutboxState.awaitingConfirmation.name,
                  OutboxState.failed.name,
                ]),
          )
          ..orderBy([(row) => OrderingTerm.asc(row.observedAt)]))
        .get();
  }

  Future<void> setState(
    String operationId,
    OutboxState state, {
    String? errorCode,
  }) async {
    await (database.update(database.outboxOperations)
          ..where((row) => row.operationId.equals(operationId)))
        .write(
      OutboxOperationsCompanion(
        state: Value(state.name),
        lastErrorCode: Value(errorCode),
      ),
    );
  }
}
