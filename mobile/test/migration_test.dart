import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:sqlite3/sqlite3.dart';

void main() {
  test('v1 to v2 keeps an outbox row while adding last_error_code', () async {
    final directory = await Directory.systemTemp.createTemp('makolo-migrate-');
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/legacy.sqlite');

    final raw = sqlite3.open(file.path);
    raw.execute('''
      CREATE TABLE outbox_operations (
        operation_id TEXT NOT NULL PRIMARY KEY,
        profile_id TEXT NOT NULL,
        device_instance_id TEXT NOT NULL,
        operation_kind TEXT NOT NULL,
        owner TEXT NOT NULL,
        resource_kind TEXT,
        resource_id TEXT,
        payload_json TEXT NOT NULL,
        dependency_ids_json TEXT NOT NULL DEFAULT '[]',
        sequence_group TEXT,
        observed_at INTEGER NOT NULL,
        state TEXT NOT NULL DEFAULT 'queued',
        attempts INTEGER NOT NULL DEFAULT 0,
        next_retry_at INTEGER,
        intent_id TEXT NOT NULL,
        owner_idempotency_key TEXT,
        replay_policy TEXT NOT NULL
      );
      INSERT INTO outbox_operations (
        operation_id, profile_id, device_instance_id, operation_kind, owner,
        payload_json, observed_at, intent_id, replay_policy
      ) VALUES (
        'op-preserved', 'profile-a', 'device-a', 'draft.save', 'Journey',
        '{}', 1, 'intent-a', 'idempotent'
      );
      PRAGMA user_version = 1;
    ''');
    raw.dispose();

    final database = MakoloDatabase(NativeDatabase(file));
    addTearDown(database.close);

    final columns = await database
        .customSelect('PRAGMA table_info(outbox_operations)')
        .get();
    expect(
      columns.map((row) => row.data['name']),
      contains('last_error_code'),
    );
    final rows =
        await database.customSelect('SELECT * FROM outbox_operations').get();
    expect(rows.single.data['operation_id'], 'op-preserved');
  });
}
