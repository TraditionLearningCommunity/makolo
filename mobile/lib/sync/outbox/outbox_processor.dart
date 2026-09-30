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
  OutboxProcessor({
    required this.repository,
    required this.handlers,
    this.reconcilers = const {},
  });

  final OutboxRepository repository;
  final Map<String, OutboxHandler> handlers;
  final Map<String, OutboxReconciler> reconcilers;

  Future<void> run() async {
    final operations = await repository.pending();
    for (final operation in operations) {
      final handler = handlers[operation.operationKind];
      if (handler == null) continue;

      final policy = _policy(operation.replayPolicy);

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

      await repository.beginAttempt(operation.operationId);

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
