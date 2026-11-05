import 'profile_file_store.dart';

typedef PrivateFileDownloader = Future<void> Function(String destinationPath);

class FileDownloadCoordinator {
  const FileDownloadCoordinator(this.store);

  final ProfileFileStore store;

  Future<StoredLocalFile> download({
    required String fileId,
    required String owner,
    required String sourceFilename,
    required String purpose,
    required String sensitivity,
    required PrivateFileDownloader downloadTo,
  }) async {
    final staged = await store.stageCopy(
      fileId: fileId,
      owner: owner,
      sourceFilename: sourceFilename,
      purpose: purpose,
      sensitivity: sensitivity,
      writeTo: downloadTo,
    );
    // A full download is already a durable FileRecord. If private
    // promotion fails (disk pressure, process interruption), preserve the
    // staged bytes so a later foreground retry does not fetch everything.
    return store.promoteToPrivate(staged.fileId);
  }
}
