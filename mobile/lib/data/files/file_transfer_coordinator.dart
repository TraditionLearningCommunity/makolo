import 'profile_file_store.dart';

typedef FileTransferProgress = void Function(int transferred, int total);

enum FileTransferState {
  localOnly,
  queued,
  transferring,
  transferred,
  failedRecoverable,
  failedTerminal,
  ownerConfirmationRequired,
}

class FileTransferReceipt {
  const FileTransferReceipt({required this.confirmed, this.remoteVersion});

  final bool confirmed;
  final String? remoteVersion;
}

class FileTransferFailure implements Exception {
  const FileTransferFailure({required this.recoverable, this.code});

  final bool recoverable;
  final String? code;
}

class FileTransferResult {
  const FileTransferResult({required this.state, this.receipt, this.errorCode});

  final FileTransferState state;
  final FileTransferReceipt? receipt;
  final String? errorCode;
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
    final result = await transferToOwner(
      fileId: fileId,
      owner: owner,
      onProgress: onProgress,
    );
    final receipt = result.receipt;
    if (result.state != FileTransferState.transferred ||
        receipt == null ||
        !receipt.confirmed) {
      throw FileTransferFailure(
        recoverable: result.state == FileTransferState.failedRecoverable,
        code: result.state == FileTransferState.ownerConfirmationRequired
            ? 'owner_confirmation_required'
            : result.errorCode,
      );
    }
    return receipt;
  }

  Future<FileTransferResult> transferToOwner({
    required String fileId,
    required FileOwnerTransfer owner,
    FileTransferProgress? onProgress,
    void Function(FileTransferState state)? onState,
  }) async {
    final file = await store.read(fileId);
    if (file == null) {
      throw StateError('Cannot transfer an unknown file record.');
    }

    onState?.call(FileTransferState.transferring);
    try {
      final receipt = await owner.upload(file: file, onProgress: onProgress);
      if (!receipt.confirmed) {
        onState?.call(FileTransferState.ownerConfirmationRequired);
        return FileTransferResult(
          state: FileTransferState.ownerConfirmationRequired,
          receipt: receipt,
        );
      }

      await store.promoteToPrivate(fileId);
      onState?.call(FileTransferState.transferred);
      return FileTransferResult(
        state: FileTransferState.transferred,
        receipt: receipt,
      );
    } on FileTransferFailure catch (error) {
      final state = error.recoverable
          ? FileTransferState.failedRecoverable
          : FileTransferState.failedTerminal;
      onState?.call(state);
      return FileTransferResult(state: state, errorCode: error.code);
    }
  }

  Future<void> cancel({
    required String fileId,
    required FileOwnerTransfer owner,
  }) {
    return owner.cancel(fileId);
  }
}
