import 'dart:io';
import 'dart:isolate';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:sqlite3/sqlite3.dart' as sql;

/// No recovery path may replace a user's database when its key is unavailable.
class ProfileDatabaseLocked implements Exception {
  const ProfileDatabaseLocked();
  @override
  String toString() =>
      'Stockage local verrouillé. Les données sont conservées.';
}

abstract interface class ProfileDatabaseKeys {
  Future<String?> read(String profileId);
  Future<void> write(String profileId, String key);
}

class SecureProfileDatabaseKeys implements ProfileDatabaseKeys {
  const SecureProfileDatabaseKeys();
  static const _storage = FlutterSecureStorage();
  String _name(String profile) => 'makolo.database.v1.$profile';
  @override
  Future<String?> read(String profileId) =>
      _storage.read(key: _name(profileId));
  @override
  Future<void> write(String profileId, String key) =>
      _storage.write(key: _name(profileId), value: key);
}

class EncryptedProfileDatabase {
  EncryptedProfileDatabase(this.file, this._key);
  final File file;
  final String _key;
  static final Map<String, Future<EncryptedProfileDatabase>> _preparing = {};

  void setup(sql.Database database) {
    try {
      if (database.select('PRAGMA cipher').isEmpty) {
        throw const ProfileDatabaseLocked();
      }
      database.execute("PRAGMA key = '$_key'");
      database.execute('PRAGMA temp_store = MEMORY');
      if (database.select('PRAGMA quick_check').single.values.single != 'ok') {
        throw const ProfileDatabaseLocked();
      }
    } on Object {
      // SQLite exceptions can contain SQL text. Never propagate a key pragma.
      throw const ProfileDatabaseLocked();
    }
  }

  static Future<EncryptedProfileDatabase> prepare({
    required String profileId,
    required Directory directory,
    ProfileDatabaseKeys keys = const SecureProfileDatabaseKeys(),
  }) {
    final scope = '${directory.absolute.path}:$profileId';
    return _preparing.putIfAbsent(
      scope,
      () => _prepare(profileId: profileId, directory: directory, keys: keys)
          .whenComplete(() {
            _preparing.remove(scope);
          }),
    );
  }

  static Future<EncryptedProfileDatabase> _prepare({
    required String profileId,
    required Directory directory,
    ProfileDatabaseKeys keys = const SecureProfileDatabaseKeys(),
  }) async {
    await directory.create(recursive: true);
    final lock = await File('${directory.path}/database-upgrade.lock')
        .open(mode: FileMode.append);
    await lock.lock(FileLock.blockingExclusive);
    try {
      final file = File('${directory.path}/makolo.encrypted.sqlite');
      final temporary = File('${file.path}.encrypting');
      var key = await keys.read(profileId);
      if (key == null) {
        if (await file.exists() || await temporary.exists()) {
          throw const ProfileDatabaseLocked();
        }
        final random = Random.secure();
        key = List.generate(
          32,
          (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
        ).join();
        await keys.write(profileId, key);
        if (await keys.read(profileId) != key) {
          throw const ProfileDatabaseLocked();
        }
      }
      if (!RegExp(r'^[0-9a-f]{64}
      final material = key;
      await Isolate.run(() => _migrate(directory.path, material));
      return EncryptedProfileDatabase(file, material);
    } on Object {
      throw const ProfileDatabaseLocked();
    } finally {
      await lock.unlock();
      await lock.close();
    }
  }

  static String _quote(String value) => "'${value.replaceAll("'", "''")}'";
  static String _identifier(String value) => '"${value.replaceAll('"', '""')}"';

  static sql.Database _open(String path, {String? key}) {
    final database = sql.sqlite3.open(path);
    try {
      if (database.select('PRAGMA cipher').isEmpty) {
        throw const ProfileDatabaseLocked();
      }
      if (key != null) database.execute('PRAGMA key = ${_quote(key)}');
      database.execute('PRAGMA temp_store = MEMORY');
      if (database.select('PRAGMA quick_check').single.values.single != 'ok') {
        throw const ProfileDatabaseLocked();
      }
      return database;
    } on Object {
      database.close();
      rethrow;
    }
  }

  static bool _sameValue(Object? a, Object? b) {
    if (a is List && b is List) {
      if (a.length != b.length) return false;
      for (var i = 0; i < a.length; i++) {
        if (!_sameValue(a[i], b[i])) return false;
      }
      return true;
    }
    return a == b;
  }

  static void _compare(sql.Database original, sql.Database encrypted) {
    final tables = original.select(
      "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    );
    final other = encrypted.select(
      "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    );
    if (tables.length != other.length) throw const ProfileDatabaseLocked();
    for (var i = 0; i < tables.length; i++) {
      if (tables[i]['name'] != other[i]['name'] ||
          tables[i]['sql'] != other[i]['sql']) {
        throw const ProfileDatabaseLocked();
      }
      final name = _identifier(tables[i]['name'] as String);
      final columns = original
          .select('PRAGMA table_info($name)')
          .map((row) => _identifier(row['name'] as String))
          .join(',');
      final left = original.select('SELECT * FROM $name ORDER BY $columns');
      final right = encrypted.select('SELECT * FROM $name ORDER BY $columns');
      if (left.length != right.length) throw const ProfileDatabaseLocked();
      for (var r = 0; r < left.length; r++) {
        if (!_sameValue(left[r].values.toList(), right[r].values.toList())) {
          throw const ProfileDatabaseLocked();
        }
      }
    }
    if (original.select('PRAGMA user_version').single.values.single !=
        encrypted.select('PRAGMA user_version').single.values.single) {
      throw const ProfileDatabaseLocked();
    }
  }

  static void _migrate(String directory, String key) {
    final original = File('$directory/makolo.sqlite');
    final encrypted = File('$directory/makolo.encrypted.sqlite');
    final temporary = File('${encrypted.path}.encrypting');
    sql.Database? source;
    sql.Database? target;
    try {
      if (original.existsSync()) {
        source = _open(original.path);
        source.execute('PRAGMA busy_timeout = 5000');
        // Keep older writers out while taking and verifying the snapshot.
        source.execute('PRAGMA locking_mode = EXCLUSIVE');
        source.execute('BEGIN EXCLUSIVE');
        source.execute('COMMIT');
        final checkpoint = source.select('PRAGMA wal_checkpoint(TRUNCATE)');
        if (checkpoint.isNotEmpty && checkpoint.first.values.first != 0) {
          throw const ProfileDatabaseLocked();
        }
      }
      if (!encrypted.existsSync() && source != null) {
        _removeDerived(temporary); // Source exists and is locked/verified.
        source.execute('VACUUM INTO ${_quote(temporary.path)}');
        target = _open(temporary.path);
        target.execute('PRAGMA rekey = ${_quote(key)}');
        target.close();
        target = null;
        target = _open(temporary.path, key: key);
        _compare(source, target);
        target.close();
        target = null;
        final durable = temporary.openSync(mode: FileMode.append);
        durable.flushSync();
        durable.closeSync();
        temporary.renameSync(encrypted.path);
      }
      if (encrypted.existsSync()) {
        target = _open(encrypted.path, key: key);
        if (source != null) _compare(source, target);
        target.close();
        target = null;
        source?.close();
        source = null;
        // Only after encrypted reopen and exact logical verification. On any
        // failure both copies remain; startup never silently chooses empty data.
        if (original.existsSync()) original.deleteSync();
        for (final suffix in ['-wal', '-shm', '-journal']) {
          final old = File('${original.path}$suffix');
          if (old.existsSync()) old.deleteSync();
        }
        _removeDerived(temporary);
      } else if (temporary.existsSync()) {
        throw const ProfileDatabaseLocked();
      }
    } finally {
      target?.close();
      source?.close();
    }
  }

  static void _removeDerived(File temporary) {
    for (final suffix in ['', '-wal', '-shm', '-journal']) {
      final file = File('${temporary.path}$suffix');
      if (file.existsSync()) file.deleteSync();
    }
  }
}
).hasMatch(key)) {
        throw const ProfileDatabaseLocked();
      }
      final material = key;
      await Isolate.run(() => _migrate(directory.path, material));
      return EncryptedProfileDatabase(file, material);
    } on Object {
      throw const ProfileDatabaseLocked();
    } finally {
      await lock.unlock();
      await lock.close();
    }
  }

  static String _quote(String value) => "'${value.replaceAll("'", "''")}'";
  static String _identifier(String value) => '"${value.replaceAll('"', '""')}"';

  static sql.Database _open(String path, {String? key}) {
    final database = sql.sqlite3.open(path);
    try {
      if (database.select('PRAGMA cipher').isEmpty) {
        throw const ProfileDatabaseLocked();
      }
      if (key != null) database.execute('PRAGMA key = ${_quote(key)}');
      database.execute('PRAGMA temp_store = MEMORY');
      if (database.select('PRAGMA quick_check').single.values.single != 'ok') {
        throw const ProfileDatabaseLocked();
      }
      return database;
    } on Object {
      database.close();
      rethrow;
    }
  }

  static bool _sameValue(Object? a, Object? b) {
    if (a is List && b is List) {
      if (a.length != b.length) return false;
      for (var i = 0; i < a.length; i++) {
        if (!_sameValue(a[i], b[i])) return false;
      }
      return true;
    }
    return a == b;
  }

  static void _compare(sql.Database original, sql.Database encrypted) {
    final tables = original.select(
      "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    );
    final other = encrypted.select(
      "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    );
    if (tables.length != other.length) throw const ProfileDatabaseLocked();
    for (var i = 0; i < tables.length; i++) {
      if (tables[i]['name'] != other[i]['name'] ||
          tables[i]['sql'] != other[i]['sql']) {
        throw const ProfileDatabaseLocked();
      }
      final name = _identifier(tables[i]['name'] as String);
      final columns = original
          .select('PRAGMA table_info($name)')
          .map((row) => _identifier(row['name'] as String))
          .join(',');
      final left = original.select('SELECT * FROM $name ORDER BY $columns');
      final right = encrypted.select('SELECT * FROM $name ORDER BY $columns');
      if (left.length != right.length) throw const ProfileDatabaseLocked();
      for (var r = 0; r < left.length; r++) {
        if (!_sameValue(left[r].values.toList(), right[r].values.toList())) {
          throw const ProfileDatabaseLocked();
        }
      }
    }
    if (original.select('PRAGMA user_version').single.values.single !=
        encrypted.select('PRAGMA user_version').single.values.single) {
      throw const ProfileDatabaseLocked();
    }
  }

  static void _migrate(String directory, String key) {
    final original = File('$directory/makolo.sqlite');
    final encrypted = File('$directory/makolo.encrypted.sqlite');
    final temporary = File('${encrypted.path}.encrypting');
    sql.Database? source;
    sql.Database? target;
    try {
      if (original.existsSync()) {
        source = _open(original.path);
        source.execute('PRAGMA busy_timeout = 5000');
        // Keep older writers out while taking and verifying the snapshot.
        source.execute('PRAGMA locking_mode = EXCLUSIVE');
        source.execute('BEGIN EXCLUSIVE');
        source.execute('COMMIT');
        final checkpoint = source.select('PRAGMA wal_checkpoint(TRUNCATE)');
        if (checkpoint.isNotEmpty && checkpoint.first.values.first != 0) {
          throw const ProfileDatabaseLocked();
        }
      }
      if (!encrypted.existsSync() && source != null) {
        _removeDerived(temporary); // Source exists and is locked/verified.
        source.execute('VACUUM INTO ${_quote(temporary.path)}');
        target = _open(temporary.path);
        target.execute('PRAGMA rekey = ${_quote(key)}');
        target.close();
        target = null;
        target = _open(temporary.path, key: key);
        _compare(source, target);
        target.close();
        target = null;
        final durable = temporary.openSync(mode: FileMode.append);
        durable.flushSync();
        durable.closeSync();
        temporary.renameSync(encrypted.path);
      }
      if (encrypted.existsSync()) {
        target = _open(encrypted.path, key: key);
        if (source != null) _compare(source, target);
        target.close();
        target = null;
        source?.close();
        source = null;
        // Only after encrypted reopen and exact logical verification. On any
        // failure both copies remain; startup never silently chooses empty data.
        if (original.existsSync()) original.deleteSync();
        for (final suffix in ['-wal', '-shm', '-journal']) {
          final old = File('${original.path}$suffix');
          if (old.existsSync()) old.deleteSync();
        }
        _removeDerived(temporary);
      } else if (temporary.existsSync()) {
        throw const ProfileDatabaseLocked();
      }
    } finally {
      target?.close();
      source?.close();
    }
  }

  static void _removeDerived(File temporary) {
    for (final suffix in ['', '-wal', '-shm', '-journal']) {
      final file = File('${temporary.path}$suffix');
      if (file.existsSync()) file.deleteSync();
    }
  }
}
