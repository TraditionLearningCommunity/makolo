import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/file_download_coordinator.dart';
import 'package:makolo_mobile/data/files/file_transfer_coordinator.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';

class AwaitingOwner implements FileOwnerTransfer {
  @override
  Future<void> cancel(String fileId) async {}

  @override
  Future<FileTransferReceipt> upload({
    required StoredLocalFile file,
    FileTransferProgress? onProgress,
  }) async => const FileTransferReceipt(confirmed: false);
}

class RecoverableOwner implements FileOwnerTransfer {
  @override
  Future<void> cancel(String fileId) async {}

  @override
  Future<FileTransferReceipt> upload({
    required StoredLocalFile file,
    FileTransferProgress? onProgress,
  }) async {
    throw const FileTransferFailure(
      recoverable: true,
      code: 'network_unreachable',
    );
  }
}

void main() {
  Future<(Directory, MakoloDatabase, ProfileFileStore)> fixture() async {
    final root = await Directory.systemTemp.createTemp('makolo-nc-transfer-');
    final database = MakoloDatabase.memory();
    final store = ProfileFileStore(
      database: database,
      profileId: 'profile-a',
      privateDirectory: Directory('${root.path}/private'),
      stagingDirectory: Directory('${root.path}/staging'),
    );
    return (root, database, store);
  }

  test('owner confirmation required is not reported as transferred', () async {
    final (root, database, store) = await fixture();
    addTearDown(() async {
      await database.close();
      await root.delete(recursive: true);
    });
    final source = File('${root.path}/source.pdf');
    await source.writeAsBytes([1]);
    await store.stage(
      fileId: 'file-1',
      owner: 'Proof',
      sourcePath: source.path,
      purpose: 'submission',
      sensitivity: 'private',
    );

    final states = <FileTransferState>[];
    final result = await FileTransferCoordinator(store).transferToOwner(
      fileId: 'file-1',
      owner: AwaitingOwner(),
      onState: states.add,
    );

    expect(result.state, FileTransferState.ownerConfirmationRequired);
    expect(states, [
      FileTransferState.transferring,
      FileTransferState.ownerConfirmationRequired,
    ]);
    expect((await store.read('file-1'))?.path, contains('/staging/'));
  });

  test('recoverable transfer failure preserves staged bytes for retry', () async {
    final (root, database, store) = await fixture();
    addTearDown(() async {
      await database.close();
      await root.delete(recursive: true);
    });
    final source = File('${root.path}/source.pdf');
    await source.writeAsBytes([1, 2]);
    await store.stage(
      fileId: 'file-2',
      owner: 'JourneyArtifact',
      sourcePath: source.path,
      purpose: 'submission',
      sensitivity: 'private',
    );

    final result = await FileTransferCoordinator(store).transferToOwner(
      fileId: 'file-2',
      owner: RecoverableOwner(),
    );

    expect(result.state, FileTransferState.failedRecoverable);
    expect(result.errorCode, 'network_unreachable');
    expect(File((await store.read('file-2'))!.path).existsSync(), isTrue);
  });

  test('private download becomes durable only after the writer succeeds', () async {
    final (root, database, store) = await fixture();
    addTearDown(() async {
      await database.close();
      await root.delete(recursive: true);
    });

    final file = await FileDownloadCoordinator(store).download(
      fileId: 'download-1',
      owner: 'Resource',
      sourceFilename: 'resource.pdf',
      purpose: 'offline-use',
      sensitivity: 'private',
      downloadTo: (destinationPath) =>
          File(destinationPath).writeAsBytes([4, 5, 6]),
    );

    expect(file.path, contains('/private/'));
    expect(await File(file.path).readAsBytes(), [4, 5, 6]);
  });
}
