import '../../data/local/makolo_database.dart';
import 'outbox_repository.dart';

enum OutboxResolution { confirmed, awaitingConfirmation, conflict, failed }

typedef OutboxHandler = Future<OutboxResolution> Function(
  OutboxOperation operation,
);

class OutboxProcessor {
  OutboxProcessor({
    required this.repository,
    required this.handlers,
  });

  final OutboxRepository repository;
  final Map<String, OutboxHandler> handlers;

  Future<void> run() async {
    final operations = await repository.pending();
    for (final operation in operations) {
      final handler = handlers[operation.operationKind];
      if (handler == null) continue;

      if (operation.state == OutboxState.failed.wireValue &&
          operation.replayPolicy == ReplayPolicy.noBlindRetry.wireValue) {
        continue;
      }

      await repository.setState(
        operation.operationId,
        OutboxState.inFlight,
      );

      try {
        final result = await handler(operation);
        await repository.setState(
          operation.operationId,
          switch (result) {
            OutboxResolution.confirmed => OutboxState.confirmed,
            OutboxResolution.awaitingConfirmation =>
              OutboxState.awaitingConfirmation,
            OutboxResolution.conflict => OutboxState.conflict,
            OutboxResolution.failed => OutboxState.failed,
          },
        );
      } on Object {
        await repository.setState(
          operation.operationId,
          operation.replayPolicy == ReplayPolicy.noBlindRetry.wireValue
              ? OutboxState.awaitingConfirmation
              : OutboxState.failed,
          errorCode: 'transport_error',
        );
      }
    }
  }
}
