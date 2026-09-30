import 'dart:async';
import 'dart:io';

import 'package:drift/drift.dart';

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
  });

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
    await stagingDirectory.create(recursive: true);
    final target = File(
      '${stagingDirectory.path}/${_safeName(fileId)}'
      '${_safeSuffix(sourceFilename)}',
    );
    if (await target.exists()) await target.delete();

    try {
      await writeTo(target.path);
      if (!await target.exists()) {
        throw FileSystemException(
          'Staging writer did not create the expected file.',
          target.path,
        );
      }
      return _record(
        fileId: fileId,
        owner: owner,
        localPath: target.path,
        purpose: purpose,
        sensitivity: sensitivity,
      );
    } on Object {
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
        .insertOnConflictUpdate(
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
    return _stored(row);
  }

  Future<List<StoredLocalFile>> stagedFiles() async {
    final rows = await (database.select(database.fileRecords)
          ..where((row) => row.profileId.equals(profileId)))
        .get();
    final root = _normalizedDirectory(stagingDirectory);
    return rows
        .map(_stored)
        .where((record) => _isInside(record.path, root))
        .toList(growable: false);
  }

  Future<int> cleanupStaging({
    required FutureOr<bool> Function(StoredLocalFile file) canRemove,
  }) async {
    var removed = 0;
    for (final file in await stagedFiles()) {
      if (!await canRemove(file)) continue;
      await remove(file.fileId);
      removed += 1;
    }
    return removed;
  }

  Future<StoredLocalFile> promoteToPrivate(String fileId) async {
    final record = await read(fileId);
    if (record == null) throw StateError('Unknown file record.');

    final current = File(record.path);
    if (!await current.exists()) {
      throw FileSystemException('Recorded file is missing.', record.path);
    }

    await privateDirectory.create(recursive: true);
    final suffix = _safeSuffix(current.uri.pathSegments.last);
    final destination = File(
      '${privateDirectory.path}/${_safeName(fileId)}$suffix',
    );
    if (await destination.exists()) await destination.delete();
    await current.copy(destination.path);
    if (current.path != destination.path && await current.exists()) {
      await current.delete();
    }

    await (database.update(database.fileRecords)..where(
          (row) => row.profileId.equals(profileId) & row.fileId.equals(fileId),
        ))
        .write(
          FileRecordsCompanion(
            localPath: Value(destination.path),
            reconstructible: const Value(false),
          ),
        );

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

  static String _normalizedDirectory(Directory directory) {
    final path = directory.absolute.path;
    return path.endsWith(Platform.pathSeparator)
        ? path
        : '$path${Platform.pathSeparator}';
  }

  static bool _isInside(String path, String normalizedRoot) {
    return File(path).absolute.path.startsWith(normalizedRoot);
  }

  static String _safeName(String value) =>
      value.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');

  static String _safeSuffix(String filename) {
    final dot = filename.lastIndexOf('.');
    if (dot < 0 || dot == filename.length - 1) return '';
    final extension = filename.substring(dot);
    return extension.replaceAll(RegExp(r'[^A-Za-z0-9.]'), '');
  }
}
