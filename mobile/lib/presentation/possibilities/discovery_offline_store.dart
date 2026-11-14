import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import '../../data/files/profile_paths.dart';

/// Explicitly retained *public* Discovery bytes. This is not a cache of
/// credentials, proof, private Journey documents, or authorization state.
/// No URLs or API tokens are written to the filesystem.
class DiscoveryOfflineStore {
  const DiscoveryOfflineStore({
    this.rootOverride,
    this.trustedOrigin,
    this.profileId,
  });

  final Directory? rootOverride;

  /// The real authenticated Profile, not the selected Space actor. Null is
  /// allowed only for openly published first-party recognition files.
  final String? profileId;

  /// The API origin supplied by trusted app configuration, never by the image.
  final Uri? trustedOrigin;
  static final Random _nonce = Random();

  static const int maxItemBytes = 20 * 1024 * 1024;
  static const int maxRecognitionBytes = 8 * 1024 * 1024;
  static const int maxAutomaticImages = 10;
  static const int maxAutomaticBytes = 32 * 1024 * 1024;

  /// A same-origin URL is not evidence of public disclosure. Automatic
  /// retention only recognizes the canonical published media-use endpoint.
  static bool isPublishedRecognitionUri(Uri url, {Uri? trustedOrigin}) {
    if (trustedOrigin == null ||
        trustedOrigin.host.isEmpty ||
        (trustedOrigin.scheme != 'http' && trustedOrigin.scheme != 'https') ||
        url.origin != trustedOrigin.origin ||
        url.host.isEmpty ||
        url.userInfo.isNotEmpty ||
        url.hasQuery ||
        url.hasFragment ||
        (url.scheme != 'http' && url.scheme != 'https')) {
      return false;
    }
    return RegExp(
      r'^/presentation/media/uses/'
      r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
      r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/file/$',
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

  bool _mayRetain(Uri url) {
    // Reader files are discretionary local copies, never authority tokens.
    // Keep signed, credentialed and unknown-scheme URLs transient only.
    if ((url.scheme != 'http' && url.scheme != 'https') ||
        url.host.isEmpty ||
        url.userInfo.isNotEmpty ||
        url.hasQuery ||
        url.hasFragment) {
      return false;
    }
    return (profileId != null && profileId!.trim().isNotEmpty) ||
        isPublishedRecognitionUri(url, trustedOrigin: trustedOrigin);
  }

  /// Legacy Reader copies were stored in one device-global directory before
  /// stage 08. Their Profile ownership cannot be reconstructed safely.
  /// Remove only this app-owned legacy directory; never touch Android's
  /// Downloads or the new Profile-scoped Reader files.
  Future<void> purgeLegacyUnscopedReader() async {
    final root = rootOverride ?? await getApplicationSupportDirectory();
    final legacy = Directory('${root.path}/discovery/public-offline');
    if (await legacy.exists()) await legacy.delete(recursive: true);
  }

  Future<Directory> _directory(Uri url) async {
    if (!_mayRetain(url)) {
      throw const FormatException(
        'This Reader resource has no safe offline Profile scope',
      );
    }
    final root = rootOverride ?? await getApplicationSupportDirectory();
    try {
      await purgeLegacyUnscopedReader();
    } on FileSystemException {
      // Legacy cleanup cannot revoke access to the newly scoped Reader.
      // It remains unreadable even if the OS prevents physical deletion.
    }
    final id = profileId;
    // Old unscoped bytes are never imported: mixed Profile provenance
    // cannot be repaired by a filename or URL inference.
    final subpath = id == null || id.isEmpty
        ? 'discovery/public-reader'
        : 'profiles/${ProfilePaths.safeProfileId(id)}/discovery/reader';
    final directory = Directory('${root.path}/$subpath');
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
    if (!isPublishedRecognitionUri(url, trustedOrigin: trustedOrigin)) {
      return null;
    }
    final file = await _recognitionFile(url);
    if (!await file.exists()) return null;
    final size = await file.length();
    if (size <= 0 || size > maxRecognitionBytes) {
      await file.delete();
      return null;
    }
    final bytes = await file.readAsBytes();
    try {
      await file.setLastModified(DateTime.now().toUtc());
    } on FileSystemException {
      // Previously received bytes remain readable.
    }
    return bytes;
  }

  // Serialize writes and quota pruning: concurrent media widgets must not
  // race to replace a staging file or delete each other's retained bytes.
  static Future<void> _pendingWrites = Future<void>.value();

  Future<void> retainRecognitionImage(Uri url, Uint8List bytes) {
    final work = _pendingWrites.then(
      (_) => _retainRecognitionImageDirect(url, bytes),
    );
    _pendingWrites = work.catchError((Object _) {});
    return work;
  }

  Future<void> _retainRecognitionImageDirect(Uri url, Uint8List bytes) async {
    if (!isPublishedRecognitionUri(url, trustedOrigin: trustedOrigin)) {
      throw const FormatException(
        'Unpublished recognition media cannot persist',
      );
    }
    if (bytes.isEmpty || bytes.length > maxRecognitionBytes) {
      throw const FormatException('Invalid published recognition image');
    }
    final target = await _recognitionFile(url);
    final nonce =
        '${DateTime.now().microsecondsSinceEpoch}-'
        '${_nonce.nextInt(1 << 32)}';
    final partial = File('${target.path}.part-$nonce');
    try {
      await partial.writeAsBytes(bytes, flush: true);
      // Preserve previously retained bytes if rename fails on this filesystem.
      final backup = File('${target.path}.backup-$nonce');
      var hadTarget = false;
      try {
        if (await target.exists()) {
          await target.rename(backup.path);
          hadTarget = true;
        }
        await partial.rename(target.path);
      } catch (_) {
        if (hadTarget && await backup.exists()) {
          if (await target.exists()) await target.delete();
          await backup.rename(target.path);
        }
        rethrow;
      }
      if (await backup.exists()) await backup.delete();
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

  /// A Discovery owner refusal withdraws the automatically retained public
  /// *recognition* images. Explicitly retained Reader files are not part of
  /// this cache and are never deleted by this action. Serialization ensures
  /// an older in-flight image write cannot restore bytes after a refusal.
  Future<void> purgeAutomaticRecognition() {
    final work = _pendingWrites.then((_) async {
      final root = rootOverride ?? await getApplicationSupportDirectory();
      final directory = Directory('${root.path}/discovery/public-recognition');
      if (await directory.exists()) {
        await directory.delete(recursive: true);
      }
    });
    _pendingWrites = work.catchError((Object _) {});
    return work;
  }

  /// A verified owner withdrawal also removes explicitly retained Reader
  /// copies for the same Profile. A transport outage must never call this.
  /// The shared historical public-offline directory remains unreadable.
  Future<void> purgePrivateReader() {
    final id = profileId;
    if (id == null || id.trim().isEmpty) return Future<void>.value();
    final work = _pendingWrites.then((_) async {
      final root = rootOverride ?? await getApplicationSupportDirectory();
      final dir = Directory(
        '${root.path}/profiles/${ProfilePaths.safeProfileId(id)}/discovery/reader',
      );
      if (await dir.exists()) await dir.delete(recursive: true);
    });
    _pendingWrites = work.catchError((Object _) {});
    return work;
  }

  Future<void> removeRecognitionImage(Uri url) {
    // Revocation must follow pending writes, or an in-flight download could
    // put the image back after the owner returned 403/404.
    final work = _pendingWrites.then((_) async {
      final target = await _recognitionFile(url);
      if (await target.exists()) await target.delete();
    });
    _pendingWrites = work.catchError((Object _) {});
    return work;
  }

  Future<File> location(Uri url) async {
    final directory = await _directory(url);
    return File('${directory.path}/${keyFor(url)}.data');
  }

  Future<File?> retained(Uri url) async {
    if (!_mayRetain(url)) return null;
    final file = await location(url);
    return await file.exists() && await file.length() > 0 ? file : null;
  }

  Future<File> save(Uri url, File source) {
    final work = _pendingWrites.then((_) => _saveDirect(url, source));
    _pendingWrites = work.then<void>((_) {}).catchError((Object _) {});
    return work;
  }

  Future<File> _saveDirect(Uri url, File source) async {
    final size = await source.length();
    if (size <= 0 || size > maxItemBytes) {
      throw const FileSystemException(
        'Fichier indisponible ou trop volumineux',
      );
    }
    final destination = await location(url);
    final nonce =
        '${DateTime.now().microsecondsSinceEpoch}-'
        '${_nonce.nextInt(1 << 32)}';
    final staging = File('${destination.path}.part-$nonce');
    final backup = File('${destination.path}.backup-$nonce');
    var hadDestination = false;
    try {
      await source.copy(staging.path);
      if (await destination.exists()) {
        await destination.rename(backup.path);
        hadDestination = true;
      }
      try {
        final result = await staging.rename(destination.path);
        if (await backup.exists()) await backup.delete();
        return result;
      } catch (_) {
        if (hadDestination && await backup.exists()) {
          if (await destination.exists()) await destination.delete();
          await backup.rename(destination.path);
        }
        rethrow;
      }
    } on Object {
      if (await staging.exists()) await staging.delete();
      rethrow;
    }
  }

  Future<void> remove(Uri url) {
    final work = _pendingWrites.then((_) async {
      final file = await location(url);
      if (await file.exists()) await file.delete();
    });
    _pendingWrites = work.catchError((Object _) {});
    return work;
  }
}
