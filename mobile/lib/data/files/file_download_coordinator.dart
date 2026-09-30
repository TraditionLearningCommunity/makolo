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
    try {
      return await store.promoteToPrivate(staged.fileId);
    } on Object {
      await store.remove(staged.fileId);
      rethrow;
    }
  }
}
