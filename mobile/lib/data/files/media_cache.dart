import 'dart:io';

import '../../network/makolo_api_client.dart';
import 'profile_paths.dart';

typedef MediaDownloader = Future<void> Function(
  String destinationPath,
  MakoloCancelHandle cancel,
  TransferProgress? onProgress,
);

class ProfileMediaCache {
  ProfileMediaCache({required this.profileId, required this.directory});

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
    return await file.exists() ? file : null;
  }

  Future<File> getOrDownload(
    String key, {
    required MediaDownloader download,
    String extension = '',
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) async {
    final target = await _target(key, extension: extension);
    if (await target.exists()) return target;

    final partial = File('${target.path}.part');
    if (await partial.exists()) await partial.delete();

    final handle = cancel ?? MakoloCancelHandle();
    await download(partial.path, handle, onProgress);
    if (!await partial.exists()) {
      throw FileSystemException(
        'Downloader did not create the expected cache file.',
        partial.path,
      );
    }
    await partial.rename(target.path);
    return target;
  }

  Future<void> purge() async {
    if (await directory.exists()) await directory.delete(recursive: true);
    await directory.create(recursive: true);
  }

  Future<File> _target(String key, {required String extension}) async {
    await directory.create(recursive: true);
    final safeExtension = extension.replaceAll(RegExp(r'[^A-Za-z0-9]'), '');
    final suffix = safeExtension.isEmpty ? '' : '.$safeExtension';
    return File('${directory.path}/${_stableKey(key)}$suffix');
  }

  static String _stableKey(String value) {
    var hash = 0x811c9dc5;
    for (final unit in value.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    return hash.toRadixString(16).padLeft(8, '0');
  }
}
