import 'dart:convert';

import '../../data/local/makolo_database.dart';
import 'outbox_repository.dart';

enum OutboxResolution {
  confirmed,
  retryable,
  awaitingConfirmation,
  conflict,
  failed,
}

typedef OutboxHandler = Future<OutboxResolution> Function(
  OutboxOperation operation,
);

typedef OutboxReconciler = Future<OutboxResolution> Function(
  OutboxOperation operation,
);

class OutboxProcessor {
  static final Expando<Set<String>> _activeClaims =
      Expando<Set<String>>('outbox-claims-per-database');
  OutboxProcessor({
    required this.repository,
    required this.handlers,
    this.reconcilers = const {},
  });

  final OutboxRepository repository;
  final Map<String, OutboxHandler> handlers;
  final Map<String, OutboxReconciler> reconcilers;
  Future<void>? _running;
  bool _active = true;

  void deactivate() => _active = false;

  /// Reconnection, app resume and manual refresh share the same drain.
  Future<void> run() {
    if (!_active) return Future<void>.value();
    final existing = _running;
    if (existing != null) return existing;
    final future = _drain();
    _running = future;
    return future.whenComplete(() => _running = null);
  }

  Future<void> _drain() async {
    final operations = await repository.pending();
    for (final operation in operations) {
      if (!_active) return;
      final claims = _activeClaims[repository.database] ??= <String>{};
      final claimKey = '${repository.profileId}:${operation.operationId}';
      if (!claims.add(claimKey)) continue;
      try {
      final handler = handlers[operation.operationKind];
      if (handler == null) continue;

      final policy = _policy(operation.replayPolicy);
      if (policy.requiresOwnerIdempotency &&
          (operation.ownerIdempotencyKey == null ||
           operation.ownerIdempotencyKey!.isEmpty)) {
        await repository.setState(
          operation.operationId,
          OutboxState.awaitingConfirmation,
          errorCode: 'idempotency_key_required',
        );
        continue;
      }

      // Dependencies must have been explicitly confirmed by this Profile.
      // A missing/foreign dependency is not evidence of authorization.
      List<String> dependencies;
      try {
        final decoded = jsonDecode(operation.dependencyIdsJson);
        if (decoded is! List || decoded.any((item) =>
            item is! String || item.isEmpty)) {
          throw const FormatException('Invalid Outbox dependencies');
        }
        dependencies = decoded.cast<String>();
      } on Object {
        await repository.setState(
          operation.operationId,
          OutboxState.awaitingConfirmation,
          errorCode: 'invalid_dependencies',
        );
        continue;
      }
      if (dependencies.contains(operation.operationId)) {
        await repository.setState(
          operation.operationId,
          OutboxState.conflict,
          errorCode: 'self_dependency',
        );
        continue;
      }
      if (dependencies.isNotEmpty) {
        final states = await repository.dependencyStates(dependencies);
        if (dependencies.any((id) =>
            states[id] == OutboxState.conflict.wireValue ||
            states[id] == OutboxState.cancelled.wireValue ||
            states[id] == OutboxState.failed.wireValue)) {
          await repository.setState(
            operation.operationId,
            OutboxState.conflict,
            errorCode: 'dependency_unavailable',
          );
          continue;
        }
        if (dependencies.any((id) =>
            states[id] != OutboxState.confirmed.wireValue)) continue;
      }

      if (policy.requiresReconciliationBeforeReplay &&
          operation.state != OutboxState.queued.wireValue) {
        final resolution = await _reconcile(operation);
        if (resolution != OutboxResolution.retryable) {
          await _applyResolution(operation.operationId, resolution);
          continue;
        }
      } else if (policy.stopsOnAmbiguousResult &&
          operation.state != OutboxState.queued.wireValue) {
        await repository.setState(
          operation.operationId,
          OutboxState.awaitingConfirmation,
        );
        continue;
      }

      if (!_active) return;
      if (operation.state == OutboxState.awaitingConfirmation.wireValue &&
          !policy.requiresReconciliationBeforeReplay) continue;
      if (!await repository.claimForAttempt(
        operation.operationId,
        expectedAttempts: operation.attempts,
        expectedState: operation.state,
      )) continue;

      try {
        final result = await handler(operation);
        if (result == OutboxResolution.awaitingConfirmation &&
            policy.requiresReconciliationBeforeReplay) {
          await _applyResolution(
            operation.operationId,
            await _reconcile(operation),
          );
        } else {
          await _applyResolution(operation.operationId, result);
        }
      } on Object {
        if (policy.requiresReconciliationBeforeReplay) {
          await _applyResolution(
            operation.operationId,
            await _reconcile(operation),
            errorCode: 'ambiguous_result',
          );
        } else if (policy.stopsOnAmbiguousResult) {
          await repository.setState(
            operation.operationId,
            OutboxState.awaitingConfirmation,
            errorCode: 'ambiguous_result',
          );
        } else {
          await repository.setState(
            operation.operationId,
            OutboxState.failed,
            errorCode: 'transport_error',
          );
        }
      }
      } finally {
        claims.remove(claimKey);
      }
    }
  }

  ReplayPolicy _policy(String value) {
    return ReplayPolicy.values.firstWhere(
      (policy) => policy.wireValue == value,
      orElse: () => ReplayPolicy.noBlindRetry,
    );
  }

  Future<OutboxResolution> _reconcile(OutboxOperation operation) async {
    final reconciler = reconcilers[operation.operationKind];
    if (reconciler == null) {
      return OutboxResolution.awaitingConfirmation;
    }
    try {
      return await reconciler(operation);
    } on Object {
      return OutboxResolution.awaitingConfirmation;
    }
  }

  Future<void> _applyResolution(
    String operationId,
    OutboxResolution resolution, {
    String? errorCode,
  }) {
    return repository.setState(operationId, switch (resolution) {
      OutboxResolution.confirmed => OutboxState.confirmed,
      OutboxResolution.retryable => OutboxState.queued,
      OutboxResolution.awaitingConfirmation => OutboxState.awaitingConfirmation,
      OutboxResolution.conflict => OutboxState.conflict,
      OutboxResolution.failed => OutboxState.failed,
    }, errorCode: errorCode);
  }
}
