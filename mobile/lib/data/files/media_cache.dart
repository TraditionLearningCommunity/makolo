import 'dart:io';

import '../../network/makolo_api_client.dart';
import 'profile_paths.dart';

typedef MediaDownloader = Future<void> Function(
  String destinationPath,
  MakoloCancelHandle cancel,
  TransferProgress? onProgress,
);

class ProfileMediaCache {
  ProfileMediaCache({required this.profileId, required this.directory}) {
    if (profileId.trim().isEmpty) {
      throw ArgumentError.value(profileId, 'profileId');
    }
  }

  static const maxCachedFiles = 60;
  static const maxCachedBytes = 128 * 1024 * 1024;
  static const maxItemBytes = 20 * 1024 * 1024;

  // One foreground writer per Profile cache directory. This also sequences
  // purge after pending downloads and prevents duplicate .part races.
  static final Map<String, Future<void>> _pending = {};

  Future<T> _serialize<T>(Future<T> Function() work) {
    final key = directory.absolute.path;
    final before = _pending[key] ?? Future<void>.value();
    final next = before.then((_) => work());
    final settled = next.then<void>(
      (_) {},
      onError: (Object _, StackTrace _) {},
    );
    _pending[key] = settled;
    settled.whenComplete(() {
      if (identical(_pending[key], settled)) _pending.remove(key);
    });
    return next;
  }

  final String profileId;
  final Directory directory;

  static Future<ProfileMediaCache> open(String profileId) async {
    return ProfileMediaCache(
      profileId: profileId,
      directory: await ProfilePaths.mediaCache(profileId),
    );
  }

  Future<File?> cached(String key, {String extension = ''}) async {
    final file = await _target(key, extension: extension);
    if (!await file.exists()) return null;
    final size = await file.length();
    if (size <= 0 || size > maxItemBytes) {
      await file.delete();
      return null;
    }
    return file;
  }

  Future<File> getOrDownload(
    String key, {
    required MediaDownloader download,
    String extension = '',
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) => _serialize(() async {
    final target = await _target(key, extension: extension);
    if (await target.exists()) {
      final size = await target.length();
      if (size > 0 && size <= maxItemBytes) {
        try {
          await target.setLastModified(DateTime.now().toUtc());
        } on FileSystemException {
          // A valid previously cached file remains usable.
        }
        return target;
      }
      await target.delete();
    }

    final partial = File(
      '${target.path}.part-${DateTime.now().microsecondsSinceEpoch}',
    );
    final handle = cancel ?? MakoloCancelHandle();
    try {
      await download(partial.path, handle, onProgress);
      if (!await partial.exists()) {
        throw FileSystemException(
          'Downloader did not create the expected cache file.',
          partial.path,
        );
      }
      final size = await partial.length();
      if (size == 0 || size > maxItemBytes) {
        throw FileSystemException(
          'Media cache object is empty or above the bounded cache limit.',
          partial.path,
        );
      }
      await partial.rename(target.path);
      await _prune(protect: target);
      return target;
    } on Object {
      if (await partial.exists()) await partial.delete();
      rethrow;
    }
  });

  /// Reconstructible only; no FileRecords, drafts or owner-origin bytes in
  /// protected staging are removed by this cache operation.
  Future<void> purge() => _serialize(() async {
    if (await directory.exists()) await directory.delete(recursive: true);
    await directory.create(recursive: true);
  });

  /// Safe to run at cold start or resume, without downloading anything.
  /// It only touches reconstructible media and abandoned partials.
  Future<void> compact() => _serialize(() => _prune(protect: null));

  Future<void> _prune({File? protect}) async {
    if (!await directory.exists()) return;
    final now = DateTime.now().toUtc();
    final files = <(File, FileStat)>[];
    await for (final entry in directory.list(followLinks: false)) {
      if (entry is! File) continue;
      final stat = await entry.stat();
      if (entry.path.contains('.part-')) {
        // An interrupted download has no FileRecord and no owner meaning.
        if (stat.modified.toUtc().isBefore(
          now.subtract(const Duration(days: 1)),
        )) {
          await entry.delete();
        }
        continue;
      }
      if (stat.size <= 0 || stat.size > maxItemBytes) {
        await entry.delete();
        continue;
      }
      files.add((entry, stat));
    }
    files.sort((a, b) => b.$2.modified.compareTo(a.$2.modified));
    var bytes = 0;
    var retained = 0;
    for (final (file, stat) in files) {
      final keep =
          file.path == protect?.path ||
          (retained < maxCachedFiles && bytes + stat.size <= maxCachedBytes);
      if (keep) {
        retained++;
        bytes += stat.size;
      } else {
        await file.delete();
      }
    }
  }

  Future<File> _target(String key, {required String extension}) async {
    await directory.create(recursive: true);
    final safeExtension = extension
        .replaceAll(RegExp(r'[^A-Za-z0-9]'), '')
        .toLowerCase();
    if (safeExtension.length > 10) {
      throw ArgumentError.value(extension, 'extension');
    }
    final suffix = safeExtension.isEmpty ? '' : '.$safeExtension';
    return File('${directory.path}/${_stableKey(key)}$suffix');
  }

  static String _stableKey(String value) {
    // 64-bit stable cache key (not an authority or integrity signature).
    // The previous 32-bit hash made collisions likely in large corpora.
    var hash = 0xcbf29ce484222325;
    for (final unit in value.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x100000001b3) & 0xffffffffffffffff;
    }
    return hash.toRadixString(16).padLeft(16, '0');
  }
}
