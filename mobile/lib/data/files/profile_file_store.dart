import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:drift/drift.dart';
import 'package:path/path.dart' as p;

import '../local/makolo_database.dart';
import 'profile_paths.dart';

class StoredLocalFile {
  const StoredLocalFile({
    required this.fileId,
    required this.profileId,
    required this.owner,
    required this.path,
    required this.purpose,
    required this.sensitivity,
    required this.reconstructible,
    required this.createdAt,
  });

  final String fileId;
  final String profileId;
  final String owner;
  final String path;
  final String purpose;
  final String sensitivity;
  final bool reconstructible;
  final DateTime createdAt;
}

class ProfileFileStore {
  ProfileFileStore({
    required this.database,
    required this.profileId,
    required this.privateDirectory,
    required this.stagingDirectory,
  }) {
    if (profileId.trim().isEmpty) {
      throw ArgumentError.value(profileId, 'profileId');
    }
  }

  final MakoloDatabase database;
  final String profileId;
  final Directory privateDirectory;
  final Directory stagingDirectory;

  static Future<ProfileFileStore> open({
    required MakoloDatabase database,
    required String profileId,
  }) async {
    return ProfileFileStore(
      database: database,
      profileId: profileId,
      privateDirectory: await ProfilePaths.privateFiles(profileId),
      stagingDirectory: await ProfilePaths.stagingFiles(profileId),
    );
  }

  Future<StoredLocalFile> stage({
    required String fileId,
    required String owner,
    required String sourcePath,
    required String purpose,
    required String sensitivity,
  }) async {
    final source = File(sourcePath);
    if (!await source.exists()) {
      throw FileSystemException('Source file does not exist.', sourcePath);
    }

    return stageCopy(
      fileId: fileId,
      owner: owner,
      sourceFilename: source.uri.pathSegments.last,
      purpose: purpose,
      sensitivity: sensitivity,
      writeTo: (destinationPath) async {
        await source.copy(destinationPath);
      },
    );
  }

  Future<StoredLocalFile> stageCopy({
    required String fileId,
    required String owner,
    required String sourceFilename,
    required String purpose,
    required String sensitivity,
    required Future<void> Function(String destinationPath) writeTo,
  }) async {
    if (fileId.trim().isEmpty ||
        owner.trim().isEmpty ||
        purpose.trim().isEmpty ||
        sensitivity.trim().isEmpty) {
      throw ArgumentError(
        'FileRecord identity, owner and purpose are required',
      );
    }
    // FileRecord.file_id is a global PK in Drift v2. Never overwrite a file
    // belonging to another Profile, or an older staged intent with the same
    // ID. A new capture requires a new opaque file ID.
    final existing = await (database.select(
      database.fileRecords,
    )..where((row) => row.fileId.equals(fileId))).getSingleOrNull();
    if (existing != null) {
      throw StateError('File ID already belongs to a durable FileRecord');
    }

    await stagingDirectory.create(recursive: true);
    final suffix = _safeSuffix(sourceFilename);
    // Random physical name: source filenames, file IDs, tokens and PII never
    // become filesystem names. Each attempt is independent even after a
    // competing process loses the SQLite primary-key insert.
    final target = File(
      '${stagingDirectory.path}/stage-${_randomKey()}$suffix',
    );
    final partial = File('${target.path}.part');
    try {
      await writeTo(partial.path);
      if (!await partial.exists() || await partial.length() == 0) {
        throw FileSystemException(
          'Staging writer did not produce a complete nonempty file.',
          partial.path,
        );
      }
      await partial.rename(target.path);
      return await _record(
        fileId: fileId,
        owner: owner,
        localPath: target.path,
        purpose: purpose,
        sensitivity: sensitivity,
      );
    } on Object {
      if (await partial.exists()) await partial.delete();
      if (await target.exists()) await target.delete();
      rethrow;
    }
  }

  Future<StoredLocalFile> _record({
    required String fileId,
    required String owner,
    required String localPath,
    required String purpose,
    required String sensitivity,
  }) async {
    final now = DateTime.now().toUtc();
    await database
        .into(database.fileRecords)
        .insert(
          FileRecordsCompanion.insert(
            fileId: fileId,
            profileId: profileId,
            owner: owner,
            localPath: localPath,
            purpose: purpose,
            sensitivity: sensitivity,
            reconstructible: const Value(false),
            createdAt: now,
          ),
          mode: InsertMode.insertOrAbort,
        );

    return StoredLocalFile(
      fileId: fileId,
      profileId: profileId,
      owner: owner,
      path: localPath,
      purpose: purpose,
      sensitivity: sensitivity,
      reconstructible: false,
      createdAt: now,
    );
  }

  Future<StoredLocalFile?> read(String fileId) async {
    final query = database.select(database.fileRecords)
      ..where(
        (row) => row.profileId.equals(profileId) & row.fileId.equals(fileId),
      );
    final row = await query.getSingleOrNull();
    if (row == null) return null;
    if (!_isInside(row.localPath, privateDirectory) &&
        !_isInside(row.localPath, stagingDirectory)) {
      throw StateError('FileRecord points outside this Profile sandbox');
    }
    return _stored(row);
  }

  Future<List<StoredLocalFile>> stagedFiles() async {
    final rows = await (database.select(
      database.fileRecords,
    )..where((row) => row.profileId.equals(profileId))).get();
    return rows
        .map(_stored)
        .where((record) => _isInside(record.path, stagingDirectory))
        .toList(growable: false);
  }

  Future<int> cleanupStaging({
    required FutureOr<bool> Function(StoredLocalFile file) canRemove,
  }) async {
    var removed = 0;
    for (final file in await stagedFiles()) {
      if (!await canRemove(file) || await _referencedByLocalWork(file)) {
        continue;
      }
      await remove(file.fileId);
      removed += 1;
    }
    return removed;
  }

  /// Cleanup of orphaned transfer attempts after a crash. This never
  /// removes tracked FileRecords, user drafts or private durable copies.
  /// Recent partial files are left alone in case a writer is still active.
  Future<int> cleanupInterruptedStaging({
    Duration olderThan = const Duration(days: 1),
  }) async {
    if (olderThan <= Duration.zero) {
      throw ArgumentError.value(olderThan, 'olderThan');
    }
    if (!await stagingDirectory.exists()) return 0;
    final tracked = await (database.select(
      database.fileRecords,
    )..where((row) => row.profileId.equals(profileId))).get();
    final paths = tracked.map((row) => p.normalize(row.localPath)).toSet();
    final cutoff = DateTime.now().toUtc().subtract(olderThan);
    var removed = 0;
    await for (final entry in stagingDirectory.list(followLinks: false)) {
      if (entry is! File ||
          !p.basename(entry.path).startsWith('stage-') ||
          paths.contains(p.normalize(entry.path))) {
        continue;
      }
      final modified = (await entry.stat()).modified.toUtc();
      if (modified.isAfter(cutoff)) continue;
      await entry.delete();
      removed++;
    }
    return removed;
  }

  /// Crash leftovers from a private promotion: the last durable copy
  /// always remains in staging until FileRecords points to the destination.
  /// Do not touch any tracked private copy or older legacy filename.
  Future<int> cleanupInterruptedPrivateCopies({
    Duration olderThan = const Duration(days: 1),
  }) async {
    if (olderThan <= Duration.zero) {
      throw ArgumentError.value(olderThan, 'olderThan');
    }
    if (!await privateDirectory.exists()) return 0;
    final records = await (database.select(
      database.fileRecords,
    )..where((row) => row.profileId.equals(profileId))).get();
    final tracked = records.map((r) => p.normalize(r.localPath)).toSet();
    final cutoff = DateTime.now().toUtc().subtract(olderThan);
    var removed = 0;
    await for (final entity in privateDirectory.list(followLinks: false)) {
      if (entity is! File ||
          !p.basename(entity.path).startsWith('stage-') ||
          tracked.contains(p.normalize(entity.path))) {
        continue;
      }
      final modified = (await entity.stat()).modified.toUtc();
      if (modified.isAfter(cutoff)) continue;
      await entity.delete();
      removed++;
    }
    return removed;
  }

  /// Never delete files still named by a draft or unresolved outbox intent.
  /// This is a conservative technical reference check, not a business owner.
  Future<bool> _referencedByLocalWork(StoredLocalFile file) async {
    final drafts = await (database.select(
      database.localDrafts,
    )..where((row) => row.profileId.equals(profileId))).get();
    for (final row in drafts) {
      if (_payloadReferencesFile(row.payloadJson, file)) return true;
    }
    final operations =
        await (database.select(database.outboxOperations)..where(
              (row) =>
                  row.profileId.equals(profileId) &
                  row.state.isNotIn(['confirmed', 'cancelled']),
            ))
            .get();
    for (final row in operations) {
      if (_payloadReferencesFile(row.payloadJson, file)) return true;
    }
    return false;
  }

  bool _payloadReferencesFile(String raw, StoredLocalFile file) {
    Object? decoded;
    try {
      decoded = jsonDecode(raw);
    } on Object {
      return true; // Malformed active work is not safely disposable.
    }
    bool match(Object? value) {
      if (value is String) {
        return value == file.fileId || value == file.path;
      }
      if (value is List) return value.any(match);
      if (value is Map) return value.values.any(match);
      return false;
    }

    return match(decoded);
  }

  Future<StoredLocalFile> promoteToPrivate(String fileId) async {
    final record = await read(fileId);
    if (record == null) throw StateError('Unknown file record.');

    final current = File(record.path);
    if (!await current.exists()) {
      throw FileSystemException('Recorded file is missing.', record.path);
    }

    if (_isInside(current.path, privateDirectory)) return record;
    if (!_isInside(current.path, stagingDirectory)) {
      throw StateError('Cannot promote a file outside Profile staging');
    }
    await privateDirectory.create(recursive: true);
    final destination = File(
      '${privateDirectory.path}/${p.basename(current.path)}',
    );
    final partial = File('${destination.path}.part-${_randomKey()}');
    try {
      await current.copy(partial.path);
      if (await partial.length() == 0) {
        throw const FileSystemException('Empty promoted file');
      }
      // On a previous interrupted promotion the destination can exist while
      // SQLite still names staging. Never destroy the last staging copy.
      if (await destination.exists()) {
        await destination.delete();
      }
      await partial.rename(destination.path);
      final changed =
          await (database.update(database.fileRecords)..where(
                (row) =>
                    row.profileId.equals(profileId) &
                    row.fileId.equals(fileId) &
                    row.localPath.equals(current.path),
              ))
              .write(
                FileRecordsCompanion(
                  localPath: Value(destination.path),
                  reconstructible: const Value(false),
                ),
              );
      if (changed != 1) {
        throw StateError('FileRecord changed during private promotion');
      }
    } finally {
      if (await partial.exists()) await partial.delete();
    }
    // Only remove the old bytes AFTER the metadata points to the durable
    // copy. A crash before this line leaves two copies, not zero copies.
    try {
      if (await current.exists()) await current.delete();
    } on FileSystemException {
      // Stale staging bytes are handled by bounded orphan cleanup.
    }

    return StoredLocalFile(
      fileId: record.fileId,
      profileId: record.profileId,
      owner: record.owner,
      path: destination.path,
      purpose: record.purpose,
      sensitivity: record.sensitivity,
      reconstructible: false,
      createdAt: record.createdAt,
    );
  }

  Future<void> remove(String fileId) async {
    final record = await read(fileId);
    if (record != null) {
      final file = File(record.path);
      if (await file.exists()) await file.delete();
    }
    await (database.delete(database.fileRecords)..where(
          (row) => row.profileId.equals(profileId) & row.fileId.equals(fileId),
        ))
        .go();
  }

  StoredLocalFile _stored(FileRecord row) {
    return StoredLocalFile(
      fileId: row.fileId,
      profileId: row.profileId,
      owner: row.owner,
      path: row.localPath,
      purpose: row.purpose,
      sensitivity: row.sensitivity,
      reconstructible: row.reconstructible,
      createdAt: row.createdAt,
    );
  }

  static bool _isInside(String path, Directory directory) {
    final candidate = p.normalize(p.absolute(path));
    final root = p.normalize(p.absolute(directory.path));
    return candidate == root || p.isWithin(root, candidate);
  }

  static final Random _secureRandom = Random.secure();
  static String _randomKey() => List<int>.generate(
    16,
    (_) => _secureRandom.nextInt(256),
  ).map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();

  static String _safeSuffix(String filename) {
    final extension = p.extension(filename);
    if (!RegExp(r'^\.[A-Za-z0-9]{1,10}$').hasMatch(extension)) return '';
    return extension.toLowerCase();
  }
}
