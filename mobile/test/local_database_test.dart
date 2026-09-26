import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

void main() {
  test('projection is stored and isolated by Profile', () async {
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

    expect((await alice.readProjection('personal.now'))?.payload['items'],
        isNotEmpty);
    expect(await bob.readProjection('personal.now'), isNull);
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
