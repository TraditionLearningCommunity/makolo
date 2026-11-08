import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_paths.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

void main() {
  test('Profile SQLite paths cannot collide after identity normalization', () {
    expect(
      MakoloDatabase.profileDirectoryKey(
        '123e4567-e89b-12d3-a456-426614174000',
      ),
      '123e4567-e89b-12d3-a456-426614174000',
      reason: 'Existing canonical Profile databases keep their paths',
    );
    final values = [
      'person/a',
      'person:a',
      'person_a',
      '__encoded__',
      '__encoded__person',
      'équipe française',
    ];
    final keys = values.map(MakoloDatabase.profileDirectoryKey).toSet();
    expect(keys, hasLength(values.length));
    expect(
      values.map(ProfilePaths.safeProfileId).toSet(),
      keys,
      reason: 'SQLite, sensitive files and media must share one path boundary',
    );
    expect(() => MakoloDatabase.profileDirectoryKey(''), throwsArgumentError);
  });

  test('root projection is stored and isolated by Profile', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);

    final alice = ProfileStore(database, 'alice');
    final bob = ProfileStore(database, 'bob');

    await alice.putProjection(
      kind: 'personal.now',
      schemaVersion: 1,
      payload: {
        'items': [
          {'label': 'Préparer le dossier'},
        ],
      },
    );

    expect(
      (await alice.readProjection('personal.now'))?.payload['items'],
      isNotEmpty,
    );
    expect((await alice.readProjection('personal.now'))?.resourceKey, isEmpty);
    expect(await bob.readProjection('personal.now'), isNull);
  });

  test(
    'keyed projection read write and watch preserve Profile isolation',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);

      final alice = ProfileStore(database, 'alice');
      final bob = ProfileStore(database, 'bob');

      await alice.putProjection(
        kind: 'activity.detail',
        resourceKey: 'activity-42',
        schemaVersion: 1,
        payload: {'title': 'Formation'},
      );

      final stored = await alice.readProjection(
        'activity.detail',
        resourceKey: 'activity-42',
      );
      expect(stored?.resourceKey, 'activity-42');
      expect(stored?.payload['title'], 'Formation');
      expect(
        await bob.readProjection('activity.detail', resourceKey: 'activity-42'),
        isNull,
      );

      final watched = await alice
          .watchProjection('activity.detail', resourceKey: 'activity-42')
          .first;
      expect(watched?.payload['title'], 'Formation');

      expect(
        await alice.readProjection('activity.detail'),
        isNull,
        reason: 'Root compatibility must not alias keyed projections.',
      );
    },
  );

  test(
    'AccessCredential payloads cannot enter generic Profile snapshots',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      await expectLater(
        store.putProjection(
          kind: 'personal.access.credential',
          resourceKey: 'access-1',
          schemaVersion: 1,
          payload: {
            'representation': {'payload': 'private-test-secret'},
          },
        ),
        throwsFormatException,
      );
      expect(
        await store.readProjection(
          'personal.access.credential',
          resourceKey: 'access-1',
        ),
        isNull,
      );
    },
  );

  test(
    'resource references are searchable only while owner facts exist',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final alice = ProfileStore(database, 'alice');
      final bob = ProfileStore(database, 'bob');

      await alice.putProjection(
        kind: 'activity.detail',
        resourceKey: 'activity-a',
        schemaVersion: 1,
        payload: {'id': 'activity-a', 'title': 'Formation'},
      );
      await alice.putResourceReference(
        resourceKind: 'Activity',
        resourceId: 'activity-a',
        projectionKind: 'activity.detail',
        label: 'Formation',
      );

      final found = await alice.readKnownResources(search: 'forma');
      expect(found, hasLength(1));
      expect(found.single.id, 'activity-a');
      expect(await bob.readKnownResources(), isEmpty);
      expect(
        await alice.watchKnownResources(search: 'FORM').first,
        hasLength(1),
      );

      await alice.deleteProjection(
        'activity.detail',
        resourceKey: 'activity-a',
      );
      expect(
        await alice.readKnownResources(),
        isEmpty,
        reason: 'An orphan index pointer must never resurrect an owner fact.',
      );

      await alice.putProjection(
        kind: 'activity.detail',
        resourceKey: 'activity-a',
        schemaVersion: 1,
        payload: {'id': 'activity-a'},
        expiresAt: DateTime.now().toUtc().subtract(const Duration(minutes: 1)),
      );
      expect(await alice.readKnownResources(), isEmpty);
    },
  );

  test(
    'expired snapshots compact only orphan indexes, never local work',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final alice = ProfileStore(db, 'profile-a');
      final bob = ProfileStore(db, 'profile-b');
      final past = DateTime.now().toUtc().subtract(const Duration(hours: 1));
      await alice.putProjection(
        kind: 'activity.detail',
        resourceKey: 'activity-a',
        schemaVersion: 1,
        payload: {'title': 'expired'},
        expiresAt: past,
      );
      await alice.putResourceReference(
        resourceKind: 'Activity',
        resourceId: 'activity-a',
        projectionKind: 'activity.detail',
      );
      await bob.putProjection(
        kind: 'activity.detail',
        resourceKey: 'activity-b',
        schemaVersion: 1,
        payload: {'title': 'still known'},
      );
      await bob.putResourceReference(
        resourceKind: 'Activity',
        resourceId: 'activity-b',
        projectionKind: 'activity.detail',
      );
      final outbox = OutboxRepository(db, 'profile-a');
      final drafts = DraftRepository(
        database: db,
        outbox: outbox,
        profileId: 'profile-a',
      );
      await drafts.saveLocal(
        draftId: 'draft-keep',
        owner: 'JourneyArtifact',
        resourceKind: 'journey',
        resourceId: 'journey-1',
        payload: {'text': 'not disposable'},
      );

      expect(await alice.purgeExpiredProjections(), 1);
      expect(
        (await db.select(db.resourceIndex).get()).where(
          (row) => row.profileId == 'profile-a',
        ),
        isEmpty,
      );
      expect(await bob.readKnownResources(), hasLength(1));
      expect(
        (await drafts.read(
          owner: 'JourneyArtifact',
          resourceKind: 'journey',
          resourceId: 'journey-1',
        ))?.payload['text'],
        'not disposable',
      );
    },
  );

  test('draft and outbox are committed atomically', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final outbox = OutboxRepository(database, 'profile-a');
    final drafts = DraftRepository(
      database: database,
      outbox: outbox,
      profileId: 'profile-a',
    );

    await drafts.saveAndQueue(
      draftId: 'draft-a',
      owner: 'Questionnaires',
      resourceKind: 'Form',
      payload: {'answer': 'A'},
      operationId: 'op-draft',
      deviceInstanceId: 'device-a',
      operationKind: 'draft.save',
      intentId: 'intent-draft',
      replayPolicy: ReplayPolicy.idempotent,
    );

    expect(await database.select(database.localDrafts).get(), hasLength(1));
    expect(
      await database.select(database.outboxOperations).get(),
      hasLength(1),
    );
  });

  test('draft ID cannot overwrite a foreign Profile or owner', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final alice = DraftRepository(
      database: database,
      outbox: OutboxRepository(database, 'alice'),
      profileId: 'alice',
    );
    final bob = DraftRepository(
      database: database,
      outbox: OutboxRepository(database, 'bob'),
      profileId: 'bob',
    );
    await alice.saveLocal(
      draftId: 'space:create',
      owner: 'Organizations',
      resourceKind: 'space.creation',
      resourceId: 'new',
      payload: {'name': 'Alice'},
    );
    await expectLater(
      bob.saveLocal(
        draftId: 'space:create',
        owner: 'Organizations',
        resourceKind: 'space.creation',
        resourceId: 'new',
        payload: {'name': 'Bob'},
      ),
      throwsStateError,
    );
    expect(
      (await alice.read(
        owner: 'Organizations',
        resourceKind: 'space.creation',
        resourceId: 'new',
      ))?.payload['name'],
      'Alice',
    );
    expect(
      await bob.read(
        owner: 'Organizations',
        resourceKind: 'space.creation',
        resourceId: 'new',
      ),
      isNull,
    );
  });

  test(
    'atomic draft and queue roll back if operation cannot be inserted',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outbox = OutboxRepository(database, 'profile-a');
      final drafts = DraftRepository(
        database: database,
        outbox: outbox,
        profileId: 'profile-a',
      );
      await outbox.enqueue(
        operationId: 'occupied',
        deviceInstanceId: 'device-a',
        operationKind: 'owner.intent',
        owner: 'Owner',
        payload: {'initial': true},
        intentId: 'intent-old',
        replayPolicy: ReplayPolicy.safe,
      );

      await expectLater(
        drafts.saveAndQueue(
          draftId: 'form:req-1',
          owner: 'Questionnaires',
          resourceKind: 'form_request',
          resourceId: 'req-1',
          payload: {
            'answers': {'question': 'A'},
          },
          operationId: 'occupied',
          deviceInstanceId: 'device-a',
          operationKind: 'questionnaire.form.submit',
          intentId: 'intent-new',
          replayPolicy: ReplayPolicy.refetchBeforeRetry,
          operationPayload: {'request_id': 'req-1'},
        ),
        throwsA(isA<Exception>()),
      );
      expect(
        await drafts.read(
          owner: 'Questionnaires',
          resourceKind: 'form_request',
          resourceId: 'req-1',
        ),
        isNull,
        reason: 'A failed enqueue must roll back the draft write too',
      );
      expect(
        await database.select(database.outboxOperations).get(),
        hasLength(1),
      );
    },
  );

  test('same owner intent cannot be queued again with new payload', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final outbox = OutboxRepository(database, 'profile-a');
    Future<void> enqueue(Map<String, dynamic> payload) => outbox.enqueue(
      operationId: 'operation-1',
      deviceInstanceId: 'device-a',
      operationKind: 'owner.save',
      owner: 'Owner',
      payload: payload,
      intentId: 'stable-intent',
      replayPolicy: ReplayPolicy.safe,
    );
    await enqueue({'value': 'once'});
    await enqueue({'value': 'once'});
    expect(
      await database.select(database.outboxOperations).get(),
      hasLength(1),
    );
    await expectLater(enqueue({'value': 'different'}), throwsStateError);
  });

  test('single active form intent is enforced in one transaction', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final outbox = OutboxRepository(database, 'profile-a');
    final drafts = DraftRepository(
      database: database,
      outbox: outbox,
      profileId: 'profile-a',
    );
    await outbox.enqueue(
      operationId: 'pending-form',
      deviceInstanceId: 'device-a',
      operationKind: 'questionnaire.form.submit',
      owner: 'Questionnaires',
      resourceId: 'request-1',
      payload: {'request_id': 'request-1'},
      intentId: 'first-intent',
      replayPolicy: ReplayPolicy.refetchBeforeRetry,
    );
    await expectLater(
      drafts.saveAndQueue(
        draftId: 'questionnaire:request-1',
        owner: 'Questionnaires',
        resourceKind: 'form_request',
        resourceId: 'request-1',
        payload: {'answers': const {}},
        operationId: 'second-form',
        deviceInstanceId: 'device-a',
        operationKind: 'questionnaire.form.submit',
        intentId: 'second-intent',
        replayPolicy: ReplayPolicy.refetchBeforeRetry,
        enforceSingleActive: true,
      ),
      throwsStateError,
    );
    expect(
      await drafts.read(
        owner: 'Questionnaires',
        resourceKind: 'form_request',
        resourceId: 'request-1',
      ),
      isNull,
    );
  });

  test('outbox survives database close and reopen', () async {
    final directory = await Directory.systemTemp.createTemp('makolo-a1-');
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/profile.sqlite');

    var database = MakoloDatabase(NativeDatabase(file));
    var outbox = OutboxRepository(database, 'profile-a');
    await outbox.enqueue(
      operationId: 'op-1',
      deviceInstanceId: 'device-a',
      operationKind: 'test.save',
      owner: 'Test',
      payload: {'value': 1},
      intentId: 'intent-1',
      replayPolicy: ReplayPolicy.idempotent,
      ownerIdempotencyKey: 'owner-key-1',
    );
    await database.close();

    database = MakoloDatabase(NativeDatabase(file));
    addTearDown(database.close);
    outbox = OutboxRepository(database, 'profile-a');

    final pending = await outbox.pending();
    expect(pending, hasLength(1));
    expect(pending.single.operationId, 'op-1');
    expect(pending.single.ownerIdempotencyKey, 'owner-key-1');
  });
}
