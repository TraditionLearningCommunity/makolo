import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class ProfilePaths {
  const ProfilePaths._();

  /// Stable canonical IDs keep the existing path. Other identifiers use a
  /// reversible encoding instead of lossy substitution, so unrelated
  /// Profiles and Assets cannot collide at the filesystem boundary.
  static String safeProfileId(String profileId) {
    if (profileId.isEmpty) {
      throw ArgumentError.value(profileId, 'profileId', 'must not be empty');
    }
    const prefix = '__encoded__';
    if (!RegExp(r'[^A-Za-z0-9_-]').hasMatch(profileId) &&
        !profileId.startsWith(prefix)) {
      return profileId;
    }
    final encoded = base64Url
        .encode(utf8.encode(profileId))
        .replaceAll('=', '');
    return '$prefix$encoded';
  }

  static Future<Directory> privateRoot(String profileId) async {
    final base = await getApplicationSupportDirectory();
    final dir = Directory('${base.path}/profiles/${safeProfileId(profileId)}');
    await dir.create(recursive: true);
    return dir;
  }

  /// A denial from the Profile owner revokes the locally retained portrait.
  /// Connectivity failures must never call this removal.
  static Future<void> removePortrait(String profileId) async {
    final root = await privateRoot(profileId);
    final portrait = File('${root.path}/passport-avatar.jpg');
    if (await portrait.exists()) await portrait.delete();
  }

  static Future<Directory> privateFiles(String profileId) async {
    final root = await privateRoot(profileId);
    final dir = Directory('${root.path}/files');
    await dir.create(recursive: true);
    return dir;
  }

  static Future<Directory> stagingFiles(String profileId) async {
    final root = await privateRoot(profileId);
    final dir = Directory('${root.path}/staging');
    await dir.create(recursive: true);
    return dir;
  }

  static Future<Directory> reconstructibleCache(String profileId) async {
    final base = await getTemporaryDirectory();
    final dir = Directory('${base.path}/makolo/${safeProfileId(profileId)}');
    await dir.create(recursive: true);
    return dir;
  }

  static Future<Directory> mediaCache(String profileId) async {
    final root = await reconstructibleCache(profileId);
    final dir = Directory('${root.path}/media');
    await dir.create(recursive: true);
    return dir;
  }

  static Future<Directory> mapCache(String profileId) async {
    final root = await reconstructibleCache(profileId);
    final dir = Directory('${root.path}/maps');
    await dir.create(recursive: true);
    return dir;
  }
}
