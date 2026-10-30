import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

/// Explicitly retained *public* Discovery bytes. This is not a cache of
/// credentials, proof, private Journey documents, or authorization state.
/// No URLs or API tokens are written to the filesystem.
class DiscoveryOfflineStore {
  const DiscoveryOfflineStore({this.rootOverride});

  final Directory? rootOverride;

  static const int maxItemBytes = 20 * 1024 * 1024;
  static const int maxRecognitionBytes = 8 * 1024 * 1024;
  static const int maxAutomaticImages = 10;
  static const int maxAutomaticBytes = 32 * 1024 * 1024;

  /// A same-origin URL is not evidence of public disclosure. Automatic
  /// retention only recognizes the canonical published media-use endpoint.
  static bool isPublishedRecognitionUri(Uri url) {
    if (url.userInfo.isNotEmpty ||
        url.hasQuery ||
        url.hasFragment ||
        (url.scheme != 'http' && url.scheme != 'https')) {
      return false;
    }
    return RegExp(
      r'^/presentation/media/uses/'
      r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
      r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/file/
  static String keyFor(Uri url) {
    var hash = 0xcbf29ce484222325;
    for (final unit in url.toString().codeUnits) {
      hash ^= unit;
      hash = (hash * 0x100000001b3) & 0xffffffffffffffff;
    }
    return hash.toRadixString(16).padLeft(16, '0');
  }

  Future<Directory> _directory() async {
    final root = rootOverride ?? await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/discovery/public-offline');
    await directory.create(recursive: true);
    return directory;
  }

  /// Published Discovery card images are acquired automatically, unlike
  /// the user's explicit Reader retention in public-offline.
  Future<File> _recognitionFile(Uri url) async {
    final root = rootOverride ?? await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/discovery/public-recognition');
    await directory.create(recursive: true);
    return File('${directory.path}/${keyFor(url)}.image');
  }

  Future<Uint8List?> recognizedImage(Uri url) async {
    if (!isPublishedRecognitionUri(url)) return null;
    final file = await _recognitionFile(url);
    if (!await file.exists()) return null;
    final size = await file.length();
    if (size <= 0 || size > maxRecognitionBytes) {
      await file.delete();
      return null;
    }
    return file.readAsBytes();
  }

  Future<void> retainRecognitionImage(Uri url, Uint8List bytes) async {
    if (!isPublishedRecognitionUri(url)) {
      throw const FormatException('Unpublished recognition media cannot persist');
    }
    if (bytes.isEmpty || bytes.length > maxRecognitionBytes) {
      throw const FormatException('Invalid published recognition image');
    }
    final target = await _recognitionFile(url);
    final partial = File('${target.path}.part');
    try {
      await partial.writeAsBytes(bytes, flush: true);
      if (await target.exists()) await target.delete();
      await partial.rename(target.path);
      await _pruneRecognition(target.parent);
    } on Object {
      if (await partial.exists()) await partial.delete();
      rethrow;
    }
  }

  Future<void> _pruneRecognition(Directory directory) async {
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
      if (i >= maxAutomaticImages || bytes > maxAutomaticBytes) {
        await file.delete();
      }
    }
  }

  Future<void> removeRecognitionImage(Uri url) async {
    final target = await _recognitionFile(url);
    if (await target.exists()) await target.delete();
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
,
    ).hasMatch(url.path);
  }

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
    final root = rootOverride ?? await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/discovery/public-offline');
    await directory.create(recursive: true);
    return directory;
  }

  /// Published Discovery card images are acquired automatically, unlike
  /// the user's explicit Reader retention in public-offline.
  Future<File> _recognitionFile(Uri url) async {
    final root = rootOverride ?? await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/discovery/public-recognition');
    await directory.create(recursive: true);
    return File('${directory.path}/${keyFor(url)}.image');
  }

  Future<Uint8List?> recognizedImage(Uri url) async {
    final file = await _recognitionFile(url);
    if (!await file.exists()) return null;
    final size = await file.length();
    if (size <= 0 || size > maxRecognitionBytes) {
      await file.delete();
      return null;
    }
    return file.readAsBytes();
  }

  Future<void> retainRecognitionImage(Uri url, Uint8List bytes) async {
    if (bytes.isEmpty || bytes.length > maxRecognitionBytes) {
      throw const FormatException('Invalid published recognition image');
    }
    final target = await _recognitionFile(url);
    final partial = File('${target.path}.part');
    try {
      await partial.writeAsBytes(bytes, flush: true);
      if (await target.exists()) await target.delete();
      await partial.rename(target.path);
      await _pruneRecognition(target.parent);
    } on Object {
      if (await partial.exists()) await partial.delete();
      rethrow;
    }
  }

  Future<void> _pruneRecognition(Directory directory) async {
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
      if (i >= maxAutomaticImages || bytes > maxAutomaticBytes) {
        await file.delete();
      }
    }
  }

  Future<void> removeRecognitionImage(Uri url) async {
    final target = await _recognitionFile(url);
    if (await target.exists()) await target.delete();
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
