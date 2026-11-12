import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart' as sql;
import 'package:makolo_mobile/data/local/encrypted_profile_database.dart';

class MemoryKeys implements ProfileDatabaseKeys {
  final values = <String, String>{};
  bool locked = false;
  @override
  Future<String?> read(String profileId) async {
    if (locked) throw StateError('locked');
    return values[profileId];
  }

  @override
  Future<void> write(String profileId, String key) async {
    if (locked) throw StateError('locked');
    values[profileId] = key;
  }
}

void main() {
  late Directory directory;
  late MemoryKeys keys;
  setUp(() async {
    directory = await Directory.systemTemp.createTemp('makolo-cipher-');
    keys = MemoryKeys();
  });
  tearDown(() async {
    await directory.delete(recursive: true);
  });
  void legacy() {
    final db = sql.sqlite3.open('${directory.path}/makolo.sqlite');
    try {
      db.execute('CREATE TABLE drafts (id TEXT PRIMARY KEY, body TEXT)');
      db.execute('CREATE TABLE outbox (id TEXT PRIMARY KEY, payload TEXT)');
      db.execute("INSERT INTO drafts VALUES ('draft','Saisie conservée')");
      db.execute("INSERT INTO outbox VALUES ('intent','reference-stable')");
      db.execute('PRAGMA user_version = 2');
    } finally {
      db.dispose();
    }
  }

  test('migration preserves exact drafts/outbox and removes verified plaintext copies', () async {
    legacy();
    final media = File('${directory.path}/voice.m4a');
    await media.writeAsBytes([1, 2, 3]);
    final encrypted = await EncryptedProfileDatabase.prepare(
      profileId: 'a',
      directory: directory,
      keys: keys,
    );
    final db = sql.sqlite3.open(encrypted.file.path);
    try {
      encrypted.setup(db);
      expect(
        db.select('SELECT body FROM drafts').single['body'],
        'Saisie conservée',
      );
      expect(
        db.select('SELECT payload FROM outbox').single['payload'],
        'reference-stable',
      );
      expect(db.userVersion, 2);
    } finally {
      db.dispose();
    }
    expect(await File('${directory.path}/makolo.sqlite').exists(), false);
    expect(await File('${encrypted.file.path}.encrypting').exists(), false);
    expect(await media.readAsBytes(), [1, 2, 3]);
    expect(
      String.fromCharCodes((await encrypted.file.readAsBytes()).take(16)),
      isNot('SQLite format 3\u0000'),
    );
  });
  test('missing key never replaces an encrypted user database', () async {
    legacy();
    final encrypted = await EncryptedProfileDatabase.prepare(
      profileId: 'a',
      directory: directory,
      keys: keys,
    );
    final bytes = await encrypted.file.readAsBytes();
    keys.values.clear();
    await expectLater(
      EncryptedProfileDatabase.prepare(
        profileId: 'a',
        directory: directory,
        keys: keys,
      ),
      throwsA(isA<ProfileDatabaseLocked>()),
    );
    expect(await encrypted.file.readAsBytes(), bytes);
  });
  test('locked Keystore preserves the original database and drafts', () async {
    legacy();
    final file = File('${directory.path}/makolo.sqlite');
    final before = await file.readAsBytes();
    keys.locked = true;
    await expectLater(
      EncryptedProfileDatabase.prepare(
        profileId: 'a',
        directory: directory,
        keys: keys,
      ),
      throwsA(isA<ProfileDatabaseLocked>()),
    );
    expect(await file.readAsBytes(), before);
  });
  test(
    'interrupted derived copy is safely rebuilt from the unchanged original',
    () async {
      legacy();
      keys.values['a'] = 'a' * 64;
      await File('${directory.path}/makolo.encrypted.sqlite.encrypting')
          .writeAsBytes([1, 2, 3]);
      final encrypted = await EncryptedProfileDatabase.prepare(
        profileId: 'a',
        directory: directory,
        keys: keys,
      );
      final db = sql.sqlite3.open(encrypted.file.path);
      try {
        encrypted.setup(db);
        expect(db.select('SELECT * FROM outbox'), hasLength(1));
      } finally {
        db.dispose();
      }
    },
  );
  test('different Profiles receive independent secure keys', () async {
    await EncryptedProfileDatabase.prepare(
      profileId: 'a',
      directory: Directory('${directory.path}/a'),
      keys: keys,
    );
    await EncryptedProfileDatabase.prepare(
      profileId: 'b',
      directory: Directory('${directory.path}/b'),
      keys: keys,
    );
    expect(keys.values['a'], isNot(keys.values['b']));
  });
}
