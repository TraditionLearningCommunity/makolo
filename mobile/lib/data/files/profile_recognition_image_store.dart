import 'dart:io';
import 'dart:typed_data';

import 'profile_paths.dart';

/// Durable bytes for already received, published recognition images only.
///
/// This is a Profile-scoped file copy, not an authorization, a second media
/// owner or a cache of credentials, proofs or private Journey documents.
/// Network denial must remove it; a transport outage must not.
class ProfileRecognitionImageStore {
  const ProfileRecognitionImageStore({
    required this.profileId,
    this.rootOverride,
  });

  final String profileId;

  /// Allows filesystem tests without depending on a platform path provider.
  final Directory? rootOverride;

  static const int maxImageBytes = 8 * 1024 * 1024;
  static const int maxRetainedImages = 10;
  static const int maxRetainedBytes = 32 * 1024 * 1024;

  static String keyFor(String path) {
    var hash = 0xcbf29ce484222325;
    for (final unit in path.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x100000001b3) & 0xffffffffffffffff;
    }
    return hash.toRadixString(16).padLeft(16, '0');
  }

  Future<File> _file(String path) async {
    final root = rootOverride == null
        ? await ProfilePaths.privateRoot(profileId)
        : Directory(
            '${rootOverride!.path}/profiles/'
            '${ProfilePaths.safeProfileId(profileId)}',
          );
    final directory = Directory('${root.path}/recognition-images');
    await directory.create(recursive: true);
    return File('${directory.path}/${keyFor(path)}.image');
  }

  Future<Uint8List?> read(String path) async {
    final file = await _file(path);
    if (!await file.exists()) return null;
    final length = await file.length();
    if (length <= 0 || length > maxImageBytes) {
      await file.delete();
      return null;
    }
    return file.readAsBytes();
  }

  Future<void> save(String path, Uint8List bytes) async {
    if (bytes.isEmpty || bytes.length > maxImageBytes) {
      throw const FormatException('Invalid recognition image');
    }
    final destination = await _file(path);
    final partial = File('${destination.path}.part');
    try {
      await partial.writeAsBytes(bytes, flush: true);
      if (await destination.exists()) await destination.delete();
      await partial.rename(destination.path);
      await _prune(destination.parent);
    } on Object {
      if (await partial.exists()) await partial.delete();
      rethrow;
    }
  }

  Future<void> _prune(Directory directory) async {
    final files = await directory
        .list()
        .where((entry) => entry is File && entry.path.endsWith('.image'))
        .cast<File>()
        .toList();
    final entries = <(File, FileStat)>[];
    for (final file in files) {
      entries.add((file, await file.stat()));
    }
    entries.sort((a, b) => b.$2.modified.compareTo(a.$2.modified));
    var bytes = 0;
    for (var i = 0; i < entries.length; i++) {
      final (file, stat) = entries[i];
      bytes += stat.size;
      if (i >= maxRetainedImages || bytes > maxRetainedBytes) {
        await file.delete();
      }
    }
  }

  Future<void> remove(String path) async {
    final file = await _file(path);
    if (await file.exists()) await file.delete();
  }

  /// Explicit owner revocation can purge the whole retained recognition set.
  /// Transport timeouts and cache cleaning never call this method.
  Future<void> purge() async {
    final root = rootOverride == null
        ? await ProfilePaths.privateRoot(profileId)
        : Directory(
            '${rootOverride!.path}/profiles/'
            '${ProfilePaths.safeProfileId(profileId)}',
          );
    final directory = Directory('${root.path}/recognition-images');
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }
}
