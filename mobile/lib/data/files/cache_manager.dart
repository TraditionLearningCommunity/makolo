import 'dart:io';

import 'profile_paths.dart';

class ReconstructibleCache {
  const ReconstructibleCache(this.profileId);

  final String profileId;

  Future<void> clear() async {
    final directory = await ProfilePaths.reconstructibleCache(profileId);
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }

  Future<File> file(String relativeName) async {
    final directory = await ProfilePaths.reconstructibleCache(profileId);
    final safe = relativeName.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
    return File('${directory.path}/$safe');
  }
}
