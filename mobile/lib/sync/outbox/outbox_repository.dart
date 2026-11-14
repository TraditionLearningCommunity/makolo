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

class OutboxConflictDetail {
  const OutboxConflictDetail({
    required this.operationKind,
    required this.owner,
    this.errorCode,
  });

  final String operationKind;
  final String owner;
  final String? errorCode;
}

class OutboxResourceOperation {
  const OutboxResourceOperation({
    required this.state,
    this.retryScheduled = false,
  });

  final String state;

  /// A temporary failure will be retried; submitting a second intent is
  /// unsafe while the original owner mutation remains unresolved.
  final bool retryScheduled;
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
  OutboxRepository(this.database, this.profileId) {
    if (profileId.trim().isEmpty) {
      throw ArgumentError.value(profileId, 'profileId');
    }
  }

  /// A claim is durable across multiple SQLite connections and a process
  /// restart. A crashed attempt is reconsidered only when its lease expires.
  static const attemptLease = Duration(minutes: 2);
  static const retryableErrorCodes = <String>{
    'transport_error',
    'owner_temporarily_unavailable',
  };

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
    return database.transaction(() async {
      if (operationId.trim().isEmpty ||
          deviceInstanceId.trim().isEmpty ||
          operationKind.trim().isEmpty ||
          owner.trim().isEmpty ||
          intentId.trim().isEmpty) {
        throw ArgumentError('Outbox identity and owner must be explicit');
      }
      if (dependencies.any((id) => id.trim().isEmpty)) {
        throw ArgumentError('Outbox dependencies must have stable identities');
      }
      // The same user intent is not a new action after a double tap or retry.
      // Reusing an intent with different content must fail, never overwrite
      // an already dispatched operation.
      final sameIntent =
          await (database.select(database.outboxOperations)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.intentId.equals(intentId),
              ))
              .get();
      if (sameIntent.isNotEmpty) {
        if (sameIntent.length != 1 ||
            sameIntent.single.operationId != operationId ||
            sameIntent.single.deviceInstanceId != deviceInstanceId ||
            sameIntent.single.owner != owner ||
            sameIntent.single.operationKind != operationKind ||
            sameIntent.single.resourceKind != resourceKind ||
            sameIntent.single.resourceId != resourceId ||
            sameIntent.single.payloadJson != jsonEncode(payload) ||
            sameIntent.single.dependencyIdsJson != jsonEncode(dependencies) ||
            sameIntent.single.replayPolicy != replayPolicy.wireValue ||
            sameIntent.single.ownerIdempotencyKey != ownerIdempotencyKey) {
          throw StateError(
            'An outbox intent cannot be changed or replayed as new',
          );
        }
        return;
      }
      await database
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
    });
  }

  Future<List<OutboxOperation>> pending() async {
    final rows =
        await (database.select(database.outboxOperations)
              ..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    (row.state.isIn([
                          OutboxState.queued.wireValue,
                          OutboxState.inFlight.wireValue,
                          OutboxState.awaitingConfirmation.wireValue,
                        ]) |
                        (row.state.equals(OutboxState.failed.wireValue) &
                            row.lastErrorCode.isIn(
                              retryableErrorCodes.toList(),
                            ))),
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
          .map(
            (row) => OutboxResourceOperation(
              state: row.state,
              retryScheduled:
                  row.state == OutboxState.failed.wireValue &&
                  retryableErrorCodes.contains(row.lastErrorCode),
            ),
          )
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
            (row.state.isIn([
                  OutboxState.queued.wireValue,
                  OutboxState.inFlight.wireValue,
                  OutboxState.awaitingConfirmation.wireValue,
                ]) |
                (row.state.equals(OutboxState.failed.wireValue) &
                    row.lastErrorCode.isIn(retryableErrorCodes.toList()))),
      )
      ..orderBy([(row) => OrderingTerm.desc(row.observedAt)])
      ..limit(1);
    return query.getSingleOrNull();
  }

  /// Profile-scoped diagnostics only: no payload or private identifiers
  /// are disclosed to the global UI.
  Future<List<OutboxConflictDetail>> readConflicts() async {
    final rows =
        await (database.select(database.outboxOperations)
              ..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.state.equals(OutboxState.conflict.wireValue),
              )
              ..orderBy([(row) => OrderingTerm.desc(row.observedAt)]))
            .get();
    return rows
        .map(
          (row) => OutboxConflictDetail(
            operationKind: row.operationKind,
            owner: row.owner,
            errorCode: row.lastErrorCode,
          ),
        )
        .toList(growable: false);
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

  /// Called only after a successful authenticated owner refresh. An HTTP
  /// 401 suspends dispatch but must not strand safe/idempotent intentions
  /// forever after a legitimate new session is established. Other policies
  /// continue to require explicit owner reconciliation or human verification.
  Future<int> releaseAuthenticatedReplayables() {
    return (database.update(database.outboxOperations)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.state.equals(OutboxState.awaitingConfirmation.wireValue) &
              row.lastErrorCode.isIn([
                'authentication_required',
                'profile_context_changed',
              ]) &
              row.replayPolicy.isIn([
                ReplayPolicy.safe.wireValue,
                ReplayPolicy.idempotent.wireValue,
              ]),
        ))
        .write(
          const OutboxOperationsCompanion(
            state: Value('queued'),
            lastErrorCode: Value(null),
            nextRetryAt: Value(null),
          ),
        );
  }

  /// Cancel only an intention that has never been dispatched. A user cannot
  /// revoke an owner mutation simply by hiding an in-flight local record.
  /// The associated local draft remains available for editing.
  Future<bool> cancelUnsent(String operationId) async {
    final changed =
        await (database.update(database.outboxOperations)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.operationId.equals(operationId) &
                  row.state.equals(OutboxState.queued.wireValue) &
                  row.attempts.equals(0),
            ))
            .write(
              const OutboxOperationsCompanion(
                state: Value('cancelled'),
                nextRetryAt: Value(null),
                lastErrorCode: Value(null),
              ),
            );
    return changed == 1;
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
    final now = DateTime.now().toUtc();
    final changed =
        await (database.update(database.outboxOperations)..where(
              (candidate) =>
                  candidate.profileId.equals(profileId) &
                  candidate.operationId.equals(operationId) &
                  candidate.state.equals(expectedState) &
                  candidate.attempts.equals(expectedAttempts) &
                  (candidate.nextRetryAt.isNull() |
                      candidate.nextRetryAt.isSmallerOrEqualValue(now)),
            ))
            .write(
              OutboxOperationsCompanion(
                state: Value(OutboxState.inFlight.wireValue),
                attempts: Value(expectedAttempts + 1),
                nextRetryAt: Value(now.add(attemptLease)),
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
    final rows =
        await (database.select(database.outboxOperations)..where(
              (row) =>
                  row.profileId.equals(profileId) & row.operationId.isIn(ids),
            ))
            .get();
    return {for (final row in rows) row.operationId: row.state};
  }

  /// A retryable transport failure is not a terminal dependency refusal.
  /// Dependents wait for its owner confirmation rather than becoming conflict.
  Future<Set<String>> permanentlyFailedDependencies(
    Iterable<String> operationIds,
  ) async {
    final ids = operationIds.toSet();
    if (ids.isEmpty) return const <String>{};
    final rows =
        await (database.select(database.outboxOperations)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.operationId.isIn(ids) &
                  row.state.equals(OutboxState.failed.wireValue),
            ))
            .get();
    return {
      for (final row in rows)
        if (!retryableErrorCodes.contains(row.lastErrorCode)) row.operationId,
    };
  }

  /// Next due retry/lease for the foreground lifecycle coordinator.
  /// No new OS job or background scheduler is introduced.
  Future<DateTime?> nextAutomaticRetryAt({Set<String>? handledKinds}) async {
    if (handledKinds != null && handledKinds.isEmpty) return null;
    final rows =
        await (database.select(database.outboxOperations)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  (row.state.equals(OutboxState.inFlight.wireValue) |
                      (row.state.equals(OutboxState.failed.wireValue) &
                          row.lastErrorCode.isIn(
                            retryableErrorCodes.toList(),
                          ))),
            ))
            .get();
    DateTime? next;
    for (final row in rows) {
      if (handledKinds != null && !handledKinds.contains(row.operationKind)) {
        continue;
      }
      final candidate = row.nextRetryAt?.toUtc();
      if (candidate != null && (next == null || candidate.isBefore(next))) {
        next = candidate;
      }
    }
    return next;
  }

  /// Cyclic dependencies cannot be resolved by a reconnection. Never send an
  /// operation while its prerequisites can eventually depend on itself.
  Future<bool> hasDependencyCycle(
    String operationId,
    Iterable<String> dependencies,
  ) async {
    final rows = await (database.select(
      database.outboxOperations,
    )..where((row) => row.profileId.equals(profileId))).get();
    final byId = {for (final row in rows) row.operationId: row};
    final seen = <String>{};
    final pending = dependencies.toList();
    while (pending.isNotEmpty) {
      final key = pending.removeLast();
      if (key == operationId) return true;
      if (!seen.add(key)) continue;
      if (seen.length > 256) return true; // fail closed on broken graphs
      final row = byId[key];
      if (row == null) continue;
      try {
        final raw = jsonDecode(row.dependencyIdsJson);
        if (raw is! List ||
            raw.any((entry) => entry is! String || entry.isEmpty)) {
          return true;
        }
        pending.addAll(raw.cast<String>());
      } on Object {
        return true;
      }
    }
    return false;
  }

  /// Backward-compatible explicit start for existing callers.
  Future<void> beginAttempt(String operationId) async {
    final row =
        await (database.select(database.outboxOperations)..where(
              (candidate) =>
                  candidate.profileId.equals(profileId) &
                  candidate.operationId.equals(operationId),
            ))
            .getSingle();
    if (!await claimForAttempt(
      operationId,
      expectedAttempts: row.attempts,
      expectedState: row.state,
    )) {
      throw StateError('Outbox operation already claimed');
    }
  }

  Future<void> setState(
    String operationId,
    OutboxState state, {
    String? errorCode,
  }) async {
    DateTime? retryAt;
    if (state == OutboxState.failed &&
        retryableErrorCodes.contains(errorCode)) {
      final operation =
          await (database.select(database.outboxOperations)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.operationId.equals(operationId),
              ))
              .getSingleOrNull();
      if (operation == null) return;
      // Bounded exponential backoff: 10s, 20s, 40s... max 5 min.
      final exponent = (operation.attempts - 1).clamp(0, 5).toInt();
      final seconds = (10 * (1 << exponent)).clamp(10, 300).toInt();
      retryAt = DateTime.now().toUtc().add(Duration(seconds: seconds));
    }
    await (database.update(database.outboxOperations)..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.operationId.equals(operationId),
        ))
        .write(
          OutboxOperationsCompanion(
            state: Value(state.wireValue),
            nextRetryAt: Value(retryAt),
            lastErrorCode: Value(errorCode),
          ),
        );
  }
}
