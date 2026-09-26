import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/sync/outbox/outbox_processor.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

void main() {
  test('retry keeps the same intent and confirms exactly once', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final repository = OutboxRepository(database, 'profile-a');

    await repository.enqueue(
      operationId: 'op-1',
      deviceInstanceId: 'device-a',
      operationKind: 'resource.reuse',
      owner: 'PersonalAssets',
      payload: {'version_id': 'v1'},
      intentId: 'intent-stable',
      replayPolicy: ReplayPolicy.idempotent,
      ownerIdempotencyKey: 'same-owner-key',
    );

    var calls = 0;
    final processor = OutboxProcessor(
      repository: repository,
      handlers: {
        'resource.reuse': (operation) async {
          calls += 1;
          expect(operation.intentId, 'intent-stable');
          expect(operation.ownerIdempotencyKey, 'same-owner-key');
          return OutboxResolution.confirmed;
        },
      },
    );

    await processor.run();
    await processor.run();

    expect(calls, 1);
    final row = (await database.select(database.outboxOperations).get()).single;
    expect(row.state, OutboxState.confirmed.wireValue);
  });

  test(
    'no-blind-retry becomes awaiting confirmation after ambiguity',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final repository = OutboxRepository(database, 'profile-a');

      await repository.enqueue(
        operationId: 'op-ambiguous',
        deviceInstanceId: 'device-a',
        operationKind: 'form.submit',
        owner: 'Questionnaires',
        payload: {'request': 'r1'},
        intentId: 'intent-ambiguous',
        replayPolicy: ReplayPolicy.noBlindRetry,
      );

      final processor = OutboxProcessor(
        repository: repository,
        handlers: {
          'form.submit': (_) async => throw TimeoutException('ambiguous'),
        },
      );

      await processor.run();
      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(row.state, OutboxState.awaitingConfirmation.wireValue);
    },
  );
}
