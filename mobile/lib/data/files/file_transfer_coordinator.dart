import 'profile_file_store.dart';

typedef FileTransferProgress = void Function(int transferred, int total);

class FileTransferReceipt {
  const FileTransferReceipt({
    required this.confirmed,
    this.remoteVersion,
  });

  final bool confirmed;
  final String? remoteVersion;
}

abstract interface class FileOwnerTransfer {
  Future<FileTransferReceipt> upload({
    required StoredLocalFile file,
    FileTransferProgress? onProgress,
  });

  Future<void> cancel(String fileId);
}

class FileTransferCoordinator {
  const FileTransferCoordinator(this.store);

  final ProfileFileStore store;

  Future<FileTransferReceipt> uploadToOwner({
    required String fileId,
    required FileOwnerTransfer owner,
    FileTransferProgress? onProgress,
  }) async {
    final file = await store.read(fileId);
    if (file == null) {
      throw StateError('Cannot transfer an unknown file record.');
    }

    final receipt = await owner.upload(file: file, onProgress: onProgress);
    if (receipt.confirmed) await store.promoteToPrivate(fileId);
    return receipt;
  }
}
