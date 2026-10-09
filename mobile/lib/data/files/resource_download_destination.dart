import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

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
    profileId,
    assetId,
    '${safeTitle.isEmpty ? 'document' : safeTitle}-v$versionNumber',
  );
}
