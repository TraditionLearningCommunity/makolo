import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import '../network/makolo_api_client.dart';

/// Portrait du Profil actif : fichier prive durable, jamais cache OS.
///
/// Les URLs proviennent uniquement des projections autorisees du Profil.
/// La validation d'origine precede toute lecture via le transport authentifie.
class ProfilePortraitStore {
  ProfilePortraitStore(this.profileId);

  final String profileId;

  Future<File> _file() async {
    final root = await getApplicationSupportDirectory();
    final safeId = profileId.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');
    return File('${root.path}/profiles/$safeId/passport-avatar.jpg');
  }

  Future<Uint8List?> read() async {
    if (profileId.isEmpty) return null;
    final file = await _file();
    if (!await file.exists()) return null;
    try {
      final size = await file.length();
      if (size <= 0 || size > 8 * 1024 * 1024) return null;
      return await file.readAsBytes();
    } on FileSystemException {
      return null;
    }
  }

  Future<void> save(Uint8List bytes) async {
    if (profileId.isEmpty || bytes.isEmpty || bytes.length > 8 * 1024 * 1024) {
      throw const FormatException('Invalid profile portrait');
    }
    final file = await _file();
    await file.parent.create(recursive: true);
    final temp = File('${file.path}.new');
    try {
      await temp.writeAsBytes(bytes, flush: true);
      if (await file.exists()) await file.delete();
      await temp.rename(file.path);
    } finally {
      if (await temp.exists()) await temp.delete();
    }
  }

  Future<void> savePickedFile(String path) async {
    final file = File(path);
    final size = await file.length();
    if (size <= 0 || size > 8 * 1024 * 1024) {
      throw const FormatException('Invalid profile portrait');
    }
    await save(await file.readAsBytes());
  }

  Future<void> clear() async {
    if (profileId.isEmpty) return;
    final file = await _file();
    if (await file.exists()) await file.delete();
  }

  /// Strictly same-origin, relative media or absolute link returned by Makolo.
  static String? authorizedPath(String? url, Uri baseUri) {
    if (url == null || url.trim().isEmpty) return null;
    final uri = Uri.tryParse(url.trim());
    if (uri == null) return null;
    final resolved = baseUri.resolveUri(uri);
    if (resolved.scheme != 'https' && resolved.scheme != 'http') return null;
    if (resolved.scheme != baseUri.scheme ||
        resolved.host != baseUri.host ||
        resolved.port != baseUri.port) {
      return null;
    }
    final path = resolved.path;
    if (!path.startsWith('/') || path.startsWith('//')) return null;
    return resolved.hasQuery ? '$path?${resolved.query}' : path;
  }

  Future<Uint8List?> refreshFromOwner({
    required MakoloApiClient api,
    required String? avatarUrl,
  }) async {
    final path = authorizedPath(avatarUrl, api.baseUri);
    if (path == null) return null;
    final bytes = await api.getPresentationImage(path);
    await save(bytes);
    return bytes;
  }
}
