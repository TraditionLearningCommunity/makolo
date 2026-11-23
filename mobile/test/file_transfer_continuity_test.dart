import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/file_download_coordinator.dart';
import 'package:makolo_mobile/data/files/file_transfer_coordinator.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

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

  test(
    'recoverable transfer failure preserves staged bytes for retry',
    () async {
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

      final result = await FileTransferCoordinator(store)
          .transferToOwner(fileId: 'file-2', owner: RecoverableOwner());

      expect(result.state, FileTransferState.failedRecoverable);
      expect(result.errorCode, 'network_unreachable');
      expect(File((await store.read('file-2'))!.path).existsSync(), isTrue);
    },
  );

  test(
    'private download becomes durable only after the writer succeeds',
    () async {
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
    },
  );
  test(
    'an interrupted download resumes its private promotion without HTTP',
    () async {
      final (root, database, store) = await fixture();
      addTearDown(() async {
        await database.close();
        await root.delete(recursive: true);
      });
      final staged = await store.stageCopy(
        fileId: 'download-recover',
        owner: 'Resource',
        sourceFilename: 'document.pdf',
        purpose: 'offline-use',
        sensitivity: 'private',
        writeTo: (path) async {
          await File(path).writeAsBytes([1, 2, 3], flush: true);
        },
      );
      var redownloaded = false;
      final completed = await FileDownloadCoordinator(store).download(
        fileId: staged.fileId,
        owner: 'Resource',
        sourceFilename: 'document.pdf',
        purpose: 'offline-use',
        sensitivity: 'private',
        downloadTo: (_) async {
          redownloaded = true;
        },
      );
      expect(redownloaded, isFalse);
      expect(completed.path, contains('/private/'));
      expect(await File(completed.path).readAsBytes(), [1, 2, 3]);

      await expectLater(
        FileDownloadCoordinator(store).download(
          fileId: staged.fileId,
          owner: 'AnotherOwner',
          sourceFilename: 'document.pdf',
          purpose: 'offline-use',
          sensitivity: 'private',
          downloadTo: (_) async {
            redownloaded = true;
          },
        ),
        throwsStateError,
      );
      expect(redownloaded, isFalse);
    },
  );

  test(
    'physical cold restart retains staged bytes, draft and owner intent',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-c5-reboot-');
      final dbPath = File('${root.path}/persistent.sqlite');
      var db = MakoloDatabase(NativeDatabase(dbPath));
      addTearDown(() async {
        await db.close();
        await root.delete(recursive: true);
      });
      ProfileFileStore files(MakoloDatabase database) => ProfileFileStore(
        database: database,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      );
      final source = File('${root.path}/source.pdf');
      await source.writeAsBytes([7, 8, 9], flush: true);
      final staged = await files(db).stage(
        fileId: 'owner-file-1',
        owner: 'JourneyArtifact',
        sourcePath: source.path,
        purpose: 'submission',
        sensitivity: 'private',
      );
      var outbox = OutboxRepository(db, 'profile-a');
      var drafts = DraftRepository(
        database: db,
        outbox: outbox,
        profileId: 'profile-a',
      );
      await drafts.saveLocal(
        draftId: 'journey-draft',
        owner: 'JourneyArtifact',
        resourceKind: 'journey_artifact',
        resourceId: 'journey-artifact-1',
        payload: {
          'attachment': {'file_id': staged.fileId},
        },
      );
      await outbox.enqueue(
        operationId: 'pending-upload',
        deviceInstanceId: 'device-a',
        operationKind: 'journey.upload',
        owner: 'JourneyArtifact',
        payload: {'file_id': staged.fileId},
        intentId: 'pending-upload-intent',
        replayPolicy: ReplayPolicy.noBlindRetry,
      );
      await db.close();

      db = MakoloDatabase(NativeDatabase(dbPath));
      outbox = OutboxRepository(db, 'profile-a');
      drafts = DraftRepository(
        database: db,
        outbox: outbox,
        profileId: 'profile-a',
      );
      final recovered = await files(db).read('owner-file-1');
      expect(recovered?.path, staged.path);
      expect(await File(recovered!.path).readAsBytes(), [7, 8, 9]);
      expect(
        (await drafts.read(
          owner: 'JourneyArtifact',
          resourceKind: 'journey_artifact',
          resourceId: 'journey-artifact-1',
        ))?.payload['attachment'],
        {'file_id': 'owner-file-1'},
      );
      expect((await outbox.pending()).single.operationId, 'pending-upload');
      expect(
        await files(db).cleanupStaging(canRemove: (_) => true),
        0,
        reason: 'A still-active local intention protects its acquired bytes',
      );
      expect(
        await files(db).promoteToPrivate('owner-file-1'),
        isA<StoredLocalFile>(),
      );
    },
  );
}
