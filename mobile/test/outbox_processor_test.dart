import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/network/api_error.dart';
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
    expect(row.attempts, 1);
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
      await processor.run();
      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(row.state, OutboxState.awaitingConfirmation.wireValue);
      expect(row.attempts, 1);
    },
  );

  test(
    'refetch-before-retry reconciles an ambiguous result with owner',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final repository = OutboxRepository(database, 'profile-a');

      await repository.enqueue(
        operationId: 'op-reconcile',
        deviceInstanceId: 'device-a',
        operationKind: 'booking.request',
        owner: 'Capacity',
        payload: {'occurrence_id': 'occ-1'},
        intentId: 'intent-reconcile',
        replayPolicy: ReplayPolicy.refetchBeforeRetry,
      );

      var ownerReads = 0;
      final processor = OutboxProcessor(
        repository: repository,
        handlers: {
          'booking.request': (_) async =>
              throw TimeoutException('lost response'),
        },
        reconcilers: {
          'booking.request': (_) async {
            ownerReads += 1;
            return OutboxResolution.confirmed;
          },
        },
      );

      await processor.run();

      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(ownerReads, 1);
      expect(row.state, OutboxState.confirmed.wireValue);
      expect(row.lastErrorCode, 'ambiguous_result');
    },
  );

  test('unknown replay policy fails closed instead of blind retry', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final repository = OutboxRepository(database, 'profile-a');

    await repository.enqueue(
      operationId: 'op-unknown',
      deviceInstanceId: 'device-a',
      operationKind: 'terminal.action',
      owner: 'Owner',
      payload: const {},
      intentId: 'intent-unknown',
      replayPolicy: ReplayPolicy.noBlindRetry,
    );
    await database.customStatement(
      "UPDATE outbox_operations SET replay_policy = 'future-policy' "
      "WHERE operation_id = 'op-unknown'",
    );

    var calls = 0;
    final processor = OutboxProcessor(
      repository: repository,
      handlers: {
        'terminal.action': (_) async {
          calls++;
          throw TimeoutException('ambiguous');
        },
      },
    );
    await processor.run();

    final row = (await database.select(database.outboxOperations).get()).single;
    expect(row.state, OutboxState.awaitingConfirmation.wireValue);
    expect(row.lastErrorCode, 'unsupported_replay_policy');
    expect(calls, 0);
  });

  test(
    'durable attempt lease prevents concurrent claims and recovers after crash',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final first = OutboxRepository(database, 'profile-a');
      final second = OutboxRepository(database, 'profile-a');
      await first.enqueue(
        operationId: 'lease-op',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.save',
        owner: 'Owner',
        payload: const {},
        intentId: 'lease-intent',
        replayPolicy: ReplayPolicy.idempotent,
        ownerIdempotencyKey: 'stable-key',
      );
      expect(
        await first.claimForAttempt(
          'lease-op',
          expectedAttempts: 0,
          expectedState: OutboxState.queued.wireValue,
        ),
        isTrue,
      );
      expect(await second.pending(), isEmpty);
      expect(
        await second.claimForAttempt(
          'lease-op',
          expectedAttempts: 1,
          expectedState: OutboxState.inFlight.wireValue,
        ),
        isFalse,
      );

      await database.customStatement(
        "UPDATE outbox_operations SET next_retry_at = 1 "
        "WHERE operation_id = 'lease-op'",
      );
      final recovered = await second.pending();
      expect(recovered, hasLength(1));
      expect(recovered.single.state, OutboxState.inFlight.wireValue);
      expect(
        await second.claimForAttempt(
          'lease-op',
          expectedAttempts: 1,
          expectedState: OutboxState.inFlight.wireValue,
        ),
        isTrue,
      );
      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(row.attempts, 2);
    },
  );

  test(
    '403 owner refusal is terminal conflict, not a replayable outage',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outbox = OutboxRepository(database, 'profile-a');
      await outbox.enqueue(
        operationId: 'owner-denial',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.action',
        owner: 'Owner',
        payload: const {},
        intentId: 'denied-intent',
        replayPolicy: ReplayPolicy.safe,
      );
      var calls = 0;
      final worker = OutboxProcessor(
        repository: outbox,
        handlers: {
          'owner.action': (_) async {
            calls++;
            throw const MakoloApiError(
              statusCode: 403,
              code: 'permission_denied',
              message: 'Denied',
            );
          },
        },
      );
      await worker.run();
      await worker.run();
      expect(calls, 1);
      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(row.state, OutboxState.conflict.wireValue);
      expect(row.lastErrorCode, 'owner_rejected');
      expect(await outbox.pending(), isEmpty);
    },
  );

  test(
    'retryable network failures back off and preserve the same intent',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outbox = OutboxRepository(database, 'profile-a');
      await outbox.enqueue(
        operationId: 'retry-op',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.action',
        owner: 'Owner',
        payload: const {},
        intentId: 'unchanged-intent',
        replayPolicy: ReplayPolicy.idempotent,
        ownerIdempotencyKey: 'stable-owner-key',
      );
      var calls = 0;
      final worker = OutboxProcessor(
        repository: outbox,
        handlers: {
          'owner.action': (operation) async {
            calls++;
            expect(operation.intentId, 'unchanged-intent');
            expect(operation.ownerIdempotencyKey, 'stable-owner-key');
            if (calls == 1) {
              throw const MakoloApiError(
                statusCode: 503,
                code: 'unavailable',
                message: 'Owner unavailable',
              );
            }
            return OutboxResolution.confirmed;
          },
        },
      );
      await worker.run();
      final failed =
          (await database.select(database.outboxOperations).get()).single;
      expect(failed.state, OutboxState.failed.wireValue);
      expect(failed.lastErrorCode, 'transport_error');
      expect(failed.nextRetryAt, isNotNull);
      await worker.run();
      expect(calls, 1, reason: 'Do not hammer an unavailable owner');
      await database.customStatement(
        "UPDATE outbox_operations SET next_retry_at = 1 "
        "WHERE operation_id = 'retry-op'",
      );
      await worker.run();
      expect(calls, 2);
      final result =
          (await database.select(database.outboxOperations).get()).single;
      expect(result.state, OutboxState.confirmed.wireValue);
      expect(result.attempts, 2);
    },
  );

  test('an owner-mismatched handler never dispatches a mutation', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final outbox = OutboxRepository(database, 'profile-a');
    await outbox.enqueue(
      operationId: 'foreign-domain',
      deviceInstanceId: 'device-a',
      operationKind: 'questionnaire.form.submit',
      owner: 'Organizations',
      payload: const {},
      intentId: 'wrong-owner',
      replayPolicy: ReplayPolicy.refetchBeforeRetry,
    );
    var invoked = false;
    await OutboxProcessor(
      repository: outbox,
      handlers: {
        'questionnaire.form.submit': (_) async {
          invoked = true;
          return OutboxResolution.confirmed;
        },
      },
      expectedOwners: const {'questionnaire.form.submit': 'Questionnaires'},
    ).run();
    expect(invoked, isFalse);
    expect(
      (await database.select(database.outboxOperations).get()).single.state,
      OutboxState.conflict.wireValue,
    );
  });

  test(
    'an owner-declared permanent failure is never blindly retried',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outbox = OutboxRepository(database, 'profile-a');
      await outbox.enqueue(
        operationId: 'permanent',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.action',
        owner: 'Owner',
        payload: const {},
        intentId: 'permanent-intent',
        replayPolicy: ReplayPolicy.safe,
      );
      var attempts = 0;
      final worker = OutboxProcessor(
        repository: outbox,
        handlers: {
          'owner.action': (_) async {
            attempts++;
            return OutboxResolution.failed;
          },
        },
      );
      await worker.run();
      await worker.run();
      expect(attempts, 1);
      expect(await outbox.pending(), isEmpty);
    },
  );

  test('only a never-dispatched intent can be locally cancelled', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final outbox = OutboxRepository(database, 'profile-a');
    await outbox.enqueue(
      operationId: 'cancel-queued',
      deviceInstanceId: 'device-a',
      operationKind: 'owner.action',
      owner: 'Owner',
      payload: const {},
      intentId: 'cancel-intent',
      replayPolicy: ReplayPolicy.safe,
    );
    expect(await outbox.cancelUnsent('cancel-queued'), isTrue);
    expect(await outbox.cancelUnsent('cancel-queued'), isFalse);
    expect(await outbox.pending(), isEmpty);

    await outbox.enqueue(
      operationId: 'already-started',
      deviceInstanceId: 'device-a',
      operationKind: 'owner.action',
      owner: 'Owner',
      payload: const {},
      intentId: 'started-intent',
      replayPolicy: ReplayPolicy.idempotent,
      ownerIdempotencyKey: 'owner-key',
    );
    await outbox.beginAttempt('already-started');
    expect(await outbox.cancelUnsent('already-started'), isFalse);
    final started = await outbox.dependencyStates(['already-started']);
    expect(started['already-started'], OutboxState.inFlight.wireValue);
  });

  test(
    'a scheduled retry remains the active intent for its resource',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outbox = OutboxRepository(database, 'profile-a');
      await outbox.enqueue(
        operationId: 'retry-form',
        deviceInstanceId: 'device-a',
        operationKind: 'questionnaire.form.submit',
        owner: 'Questionnaires',
        resourceId: 'request-a',
        payload: const {},
        intentId: 'retry-form-intent',
        replayPolicy: ReplayPolicy.refetchBeforeRetry,
      );
      await outbox.beginAttempt('retry-form');
      await outbox.setState(
        'retry-form',
        OutboxState.failed,
        errorCode: 'transport_error',
      );

      expect(
        (await outbox.activeForResource(
          operationKind: 'questionnaire.form.submit',
          resourceId: 'request-a',
        ))?.operationId,
        'retry-form',
      );
      expect(
        (await outbox
                .watchResource(
                  operationKind: 'questionnaire.form.submit',
                  resourceId: 'request-a',
                )
                .first)
            .single
            .retryScheduled,
        isTrue,
      );

      await outbox.setState(
        'retry-form',
        OutboxState.failed,
        errorCode: 'owner_rejected',
      );
      expect(
        await outbox.activeForResource(
          operationKind: 'questionnaire.form.submit',
          resourceId: 'request-a',
        ),
        isNull,
      );
    },
  );

  test(
    'reauthentication releases only explicitly replayable 401-paused intents',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final outbox = OutboxRepository(db, 'profile-a');
      for (final policy in [ReplayPolicy.safe, ReplayPolicy.noBlindRetry]) {
        await outbox.enqueue(
          operationId: 'auth-${policy.name}',
          deviceInstanceId: 'device-a',
          operationKind: 'owner.action',
          owner: 'Owner',
          payload: const {},
          intentId: 'intent-${policy.name}',
          replayPolicy: policy,
        );
      }
      var authorized = false;
      final worker = OutboxProcessor(
        repository: outbox,
        handlers: {
          'owner.action': (_) async {
            if (!authorized) {
              throw const MakoloApiError(
                statusCode: 401,
                code: 'authentication_required',
                message: 'Sign in again',
              );
            }
            return OutboxResolution.confirmed;
          },
        },
      );
      await worker.run();
      final paused = await outbox.dependencyStates([
        'auth-safe',
        'auth-noBlindRetry',
      ]);
      expect(
        paused.values,
        everyElement(OutboxState.awaitingConfirmation.wireValue),
      );

      // The application invokes this only after authenticated owner roots
      // have succeeded. It must not quietly requeue no-blind requests.
      authorized = true;
      expect(await outbox.releaseAuthenticatedReplayables(), 1);
      await worker.run();
      final resumed = await outbox.dependencyStates([
        'auth-safe',
        'auth-noBlindRetry',
      ]);
      expect(resumed['auth-safe'], OutboxState.confirmed.wireValue);
      expect(
        resumed['auth-noBlindRetry'],
        OutboxState.awaitingConfirmation.wireValue,
      );
    },
  );

  test('owner handler refuses a locally weakened replay policy', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final outbox = OutboxRepository(db, 'profile-a');
    await outbox.enqueue(
      operationId: 'form-unsafe',
      deviceInstanceId: 'device-a',
      operationKind: 'questionnaire.form.submit',
      owner: 'Questionnaires',
      payload: const {},
      intentId: 'form-unsafe-intent',
      replayPolicy: ReplayPolicy.safe,
    );
    var sent = false;
    await OutboxProcessor(
      repository: outbox,
      handlers: {
        'questionnaire.form.submit': (_) async {
          sent = true;
          return OutboxResolution.confirmed;
        },
      },
      expectedOwners: const {'questionnaire.form.submit': 'Questionnaires'},
      expectedReplayPolicies: const {
        'questionnaire.form.submit': ReplayPolicy.refetchBeforeRetry,
      },
    ).run();
    expect(sent, isFalse);
    final row = (await db.select(db.outboxOperations).get()).single;
    expect(row.state, OutboxState.awaitingConfirmation.wireValue);
    expect(row.lastErrorCode, 'unsupported_replay_policy');
  });

  test(
    'wrong Profile cannot dispatch and safe intent resumes on reauth',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final owner = OutboxRepository(database, 'profile-a');
      await owner.enqueue(
        operationId: 'guarded',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.save',
        owner: 'Owner',
        payload: const {},
        intentId: 'guarded-intent',
        replayPolicy: ReplayPolicy.safe,
      );
      var session = 'profile-b';
      var sent = 0;
      final processor = OutboxProcessor(
        repository: owner,
        handlers: {
          'owner.save': (_) async {
            sent++;
            return OutboxResolution.confirmed;
          },
        },
        canDispatch: (operation) async => operation.profileId == session,
      );

      await processor.run();
      expect(sent, 0);
      final paused =
          (await database.select(database.outboxOperations).get()).single;
      expect(paused.state, OutboxState.awaitingConfirmation.wireValue);
      expect(paused.lastErrorCode, 'profile_context_changed');

      session = 'profile-a';
      expect(await owner.releaseAuthenticatedReplayables(), 1);
      await processor.run();
      expect(sent, 1);
      expect(
        (await database.select(database.outboxOperations).get()).single.state,
        OutboxState.confirmed.wireValue,
      );
    },
  );

  test(
    'a Profile switch between claim and handler blocks the mutation',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final owner = OutboxRepository(database, 'profile-a');
      await owner.enqueue(
        operationId: 'race',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.save',
        owner: 'Owner',
        payload: const {},
        intentId: 'race-intent',
        replayPolicy: ReplayPolicy.safe,
      );
      var gateChecks = 0;
      var called = false;
      final processor = OutboxProcessor(
        repository: owner,
        handlers: {
          'owner.save': (_) async {
            called = true;
            return OutboxResolution.confirmed;
          },
        },
        canDispatch: (_) async => ++gateChecks == 1,
      );
      await processor.run();
      expect(gateChecks, 2);
      expect(called, isFalse);
      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(row.state, OutboxState.awaitingConfirmation.wireValue);
      expect(row.attempts, 1);
      expect(row.lastErrorCode, 'profile_context_changed');
    },
  );

  test(
    'Profile switch after mutation blocks owner reconciliation reads',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outbox = OutboxRepository(database, 'profile-a');
      await outbox.enqueue(
        operationId: 'await-owner',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.submit',
        owner: 'Owner',
        payload: const {},
        intentId: 'await-owner-intent',
        replayPolicy: ReplayPolicy.refetchBeforeRetry,
      );
      var activeProfile = 'profile-a';
      var reconciliations = 0;
      final processor = OutboxProcessor(
        repository: outbox,
        handlers: {
          'owner.submit': (_) async {
            activeProfile = 'profile-b';
            return OutboxResolution.awaitingConfirmation;
          },
        },
        reconcilers: {
          'owner.submit': (_) async {
            reconciliations++;
            return OutboxResolution.confirmed;
          },
        },
        canDispatch: (op) async => activeProfile == op.profileId,
      );

      await processor.run();
      expect(reconciliations, 0);
      expect(
        (await database.select(database.outboxOperations).get()).single.state,
        OutboxState.awaitingConfirmation.wireValue,
      );
      activeProfile = 'profile-a';
      await processor.run();
      expect(reconciliations, 1);
      expect(
        (await database.select(database.outboxOperations).get()).single.state,
        OutboxState.confirmed.wireValue,
      );
    },
  );
}
