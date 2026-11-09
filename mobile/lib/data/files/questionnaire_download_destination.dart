import 'dart:io';

import 'package:path_provider/path_provider.dart';

import 'profile_paths.dart';

/// Transient per-Profile directory for user-requested questionnaire media.
Future<Directory> questionnaireDownloadDirectory(String profileId) async {
  final temp = await getTemporaryDirectory();
  final dir = Directory(
    '${temp.path}/questionnaire-${ProfilePaths.safeProfileId(profileId)}',
  );
  await dir.create(recursive: true);
  return dir;
}
