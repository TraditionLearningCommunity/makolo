import 'dart:io';

import 'package:path_provider/path_provider.dart';

class ProfilePaths {
  const ProfilePaths._();

  static String _safe(String profileId) =>
      profileId.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');

  static Future<Directory> privateFiles(String profileId) async {
    final base = await getApplicationSupportDirectory();
    final dir = Directory('${base.path}/profiles/${_safe(profileId)}/files');
    await dir.create(recursive: true);
    return dir;
  }

  static Future<Directory> reconstructibleCache(String profileId) async {
    final base = await getTemporaryDirectory();
    final dir = Directory('${base.path}/makolo/${_safe(profileId)}');
    await dir.create(recursive: true);
    return dir;
  }
}
