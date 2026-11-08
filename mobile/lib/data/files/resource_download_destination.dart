import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import 'profile_paths.dart';

/// Native storage boundary for non-sensitive, user-requested resources.
Future<String> resourceDownloadDestination({
  required String profileId,
  required String assetId,
  required String title,
  required int versionNumber,
}) async {
  final directory = await getApplicationDocumentsDirectory();
  final safeTitle = title
      .replaceAll(RegExp(r'[^A-Za-z0-9._-]+'), '-')
      .replaceAll(RegExp(r'-+'), '-');
  return p.join(
    directory.path,
    'makolo',
    'resources',
    ProfilePaths.safeProfileId(profileId),
    ProfilePaths.safeProfileId(assetId),
    '${safeTitle.isEmpty ? 'document' : safeTitle}-v$versionNumber',
  );
}

/// Only the app's retained private copy is withdrawn; files explicitly
/// exported by the person into system Downloads remain user-managed.
Future<void> removeLocallyRetainedResourceVersions({
  required String profileId,
  required String assetId,
}) async {
  final root = await getApplicationDocumentsDirectory();
  final directory = Directory(
    p.join(
      root.path,
      'makolo',
      'resources',
      ProfilePaths.safeProfileId(profileId),
      ProfilePaths.safeProfileId(assetId),
    ),
  );
  if (await directory.exists()) await directory.delete(recursive: true);
}

/// Clear only Makolo's Profile-private Resource copies when the collection
/// owner explicitly withdraws all visibility. The system Downloads export
/// remains a separate user-controlled copy.
Future<void> removeAllLocallyRetainedResources(String profileId) async {
  final root = await getApplicationDocumentsDirectory();
  final directory = Directory(
    p.join(
      root.path,
      'makolo',
      'resources',
      ProfilePaths.safeProfileId(profileId),
    ),
  );
  if (await directory.exists()) await directory.delete(recursive: true);
}
