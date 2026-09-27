import 'dart:io';

import 'package:path_provider/path_provider.dart';

class ProfilePaths {
  const ProfilePaths._();

  static String safeProfileId(String profileId) =>
      profileId.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');

  static Future<Directory> privateRoot(String profileId) async {
    final base = await getApplicationSupportDirectory();
    final dir = Directory(
      '${base.path}/profiles/${safeProfileId(profileId)}',
    );
    await dir.create(recursive: true);
    return dir;
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
    final dir = Directory(
      '${base.path}/makolo/${safeProfileId(profileId)}',
    );
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
