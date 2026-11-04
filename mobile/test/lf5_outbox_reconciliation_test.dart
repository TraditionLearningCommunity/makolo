import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/sync/outbox/outbox_processor.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

Future<void> enqueue(
  OutboxRepository repo,
  String id, {
  ReplayPolicy policy = ReplayPolicy.safe,
  String? key,
  List<String> dependencies = const [],
}) => repo.enqueue(
  operationId: id,
  deviceInstanceId: 'device-test',
  operationKind: 'owner.intent',
  owner: 'Owner',
  payload: {'intent': id},
  intentId: 'intent-$id',
  replayPolicy: policy,
  ownerIdempotencyKey: key,
  dependencies: dependencies,
);

void main() {
  test('concurrent reconnect processors atomically claim an operation once',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = OutboxRepository(db, 'profile-a');
    await enqueue(repo, 'one');
    final began = Completer<void>();
    final release = Completer<OutboxResolution>();
    var calls = 0;
    OutboxHandler handler = (_) {
      calls++;
      if (!began.isCompleted) began.complete();
      return release.future;
    };
    final first = OutboxProcessor(
      repository: repo, handlers: {'owner.intent': handler},
    );
    final second = OutboxProcessor(
      repository: OutboxRepository(db, 'profile-a'),
      handlers: {'owner.intent': handler},
    );
    final running = first.run();
    await began.future;
    await second.run();
    release.complete(OutboxResolution.confirmed);
    await running;
    expect(calls, 1);
    final row = (await db.select(db.outboxOperations).get()).single;
    expect(row.attempts, 1);
    expect(row.state, OutboxState.confirmed.wireValue);
  });

  test('foreign and unresolved dependencies cannot authorize replay',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final owner = OutboxRepository(db, 'profile-a');
    final other = OutboxRepository(db, 'profile-b');
    await enqueue(other, 'foreign');
    await enqueue(owner, 'dependent', dependencies: ['foreign']);
    var calls = 0;
    final worker = OutboxProcessor(
      repository: owner,
      handlers: {'owner.intent': (_) async {
        calls++;
        return OutboxResolution.confirmed;
      }},
    );
    await worker.run();
    expect(calls, 0);
    await enqueue(owner, 'prerequisite');
    await enqueue(owner, 'next', dependencies: ['prerequisite']);
    await worker.run();
    expect(calls, 2);
    expect((await owner.dependencyStates(['prerequisite', 'next']))['next'],
        OutboxState.confirmed.wireValue);
  });

  test('idempotent mutations without owner key cannot be sent', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = OutboxRepository(db, 'profile-a');
    await enqueue(repo, 'missing-key', policy: ReplayPolicy.idempotent);
    var dispatched = false;
    await OutboxProcessor(
      repository: repo,
      handlers: {'owner.intent': (_) async {
        dispatched = true;
        return OutboxResolution.confirmed;
      }},
    ).run();
    expect(dispatched, isFalse);
    final row = (await db.select(db.outboxOperations).get()).single;
    expect(row.state, OutboxState.awaitingConfirmation.wireValue);
    expect(row.lastErrorCode, 'idempotency_key_required');
  });

  test('cyclic dependencies never send either owner mutation', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = OutboxRepository(db, 'profile-a');
    await enqueue(repo, 'alpha', dependencies: ['beta']);
    await enqueue(repo, 'beta', dependencies: ['alpha']);
    var dispatched = 0;
    await OutboxProcessor(
      repository: repo,
      handlers: {'owner.intent': (_) async {
        dispatched++;
        return OutboxResolution.confirmed;
      }},
    ).run();
    expect(dispatched, 0);
    final states = await repo.dependencyStates(['alpha', 'beta']);
    expect(states['alpha'], OutboxState.conflict.wireValue);
    expect(states['beta'], OutboxState.conflict.wireValue);
  });

  test('owner confirmation can safely release a previously ambiguous intent',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = OutboxRepository(db, 'profile-a');
    await enqueue(
      repo, 'reconciled', policy: ReplayPolicy.refetchBeforeRetry,
    );
    var ownerCanRetry = false;
    var sends = 0;
    final worker = OutboxProcessor(
      repository: repo,
      handlers: {'owner.intent': (_) async {
        sends++;
        if (sends == 1) throw TimeoutException('lost owner response');
        return OutboxResolution.confirmed;
      }},
      reconcilers: {'owner.intent': (_) async =>
          ownerCanRetry
              ? OutboxResolution.retryable
              : OutboxResolution.awaitingConfirmation},
    );
    await worker.run();
    expect((await repo.dependencyStates(['reconciled']))['reconciled'],
        OutboxState.awaitingConfirmation.wireValue);
    ownerCanRetry = true;
    await worker.run();
    expect(sends, 2);
    expect((await repo.dependencyStates(['reconciled']))['reconciled'],
        OutboxState.confirmed.wireValue);
  });

  test('crashed in-flight non-replayable action awaits owner decision',
      () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = OutboxRepository(db, 'profile-a');
    await enqueue(repo, 'ambiguous', policy: ReplayPolicy.noBlindRetry);
    await repo.beginAttempt('ambiguous');
    var called = false;
    await OutboxProcessor(
      repository: repo,
      handlers: {'owner.intent': (_) async {
        called = true;
        return OutboxResolution.confirmed;
      }},
    ).run();
    final row = (await db.select(db.outboxOperations).get()).single;
    expect(called, isFalse);
    expect(row.state, OutboxState.awaitingConfirmation.wireValue);
  });
}
