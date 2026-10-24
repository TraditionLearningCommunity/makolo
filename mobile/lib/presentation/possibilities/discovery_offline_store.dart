import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Explicitly retained *public* Discovery bytes. This is not a cache of
/// credentials, proof, private Journey documents, or authorization state.
/// No URLs or API tokens are written to the filesystem.
class DiscoveryOfflineStore {
  const DiscoveryOfflineStore();

  static const int maxItemBytes = 20 * 1024 * 1024;

  /// FNV-1a gives a stable filename; not a security or integrity signature.
  static String keyFor(Uri url) {
    var hash = 0xcbf29ce484222325;
    for (final unit in url.toString().codeUnits) {
      hash ^= unit;
      hash = (hash * 0x100000001b3) & 0xffffffffffffffff;
    }
    return hash.toRadixString(16).padLeft(16, '0');
  }

  Future<Directory> _directory() async {
    final root = await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/discovery/public-offline');
    await directory.create(recursive: true);
    return directory;
  }

  Future<File> location(Uri url) async {
    final directory = await _directory();
    return File('${directory.path}/${keyFor(url)}.data');
  }

  Future<File?> retained(Uri url) async {
    final file = await location(url);
    return await file.exists() && await file.length() > 0 ? file : null;
  }

  Future<File> save(Uri url, File source) async {
    final size = await source.length();
    if (size <= 0 || size > maxItemBytes) {
      throw const FileSystemException(
        'Fichier indisponible ou trop volumineux',
      );
    }
    final destination = await location(url);
    final staging = File('${destination.path}.part');
    try {
      if (await staging.exists()) await staging.delete();
      await source.copy(staging.path);
      if (await destination.exists()) await destination.delete();
      return await staging.rename(destination.path);
    } on Object {
      if (await staging.exists()) await staging.delete();
      rethrow;
    }
  }

  Future<void> remove(Uri url) async {
    final file = await location(url);
    if (await file.exists()) await file.delete();
  }
}
