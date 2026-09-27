import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/file_transfer_coordinator.dart';
import 'package:makolo_mobile/data/files/media_cache.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';

class ConfirmingOwnerTransfer implements FileOwnerTransfer {
  StoredLocalFile? uploaded;

  @override
  Future<FileTransferReceipt> upload({
    required StoredLocalFile file,
    FileTransferProgress? onProgress,
  }) async {
    uploaded = file;
    onProgress?.call(4, 4);
    return const FileTransferReceipt(
      confirmed: true,
      remoteVersion: 'server-version-1',
    );
  }

  @override
  Future<void> cancel(String fileId) async {}
}

void main() {
  test(
    'private staging reuses FileRecords and remains profile scoped',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-files-');
      final database = MakoloDatabase.memory();
      addTearDown(() async {
        await database.close();
        await root.delete(recursive: true);
      });

      final source = File('${root.path}/source.txt');
      await source.writeAsString('private payload');
      final staging = Directory('${root.path}/profile-a/staging');
      final private = Directory('${root.path}/profile-a/files');
      final store = ProfileFileStore(
        database: database,
        profileId: 'profile-a',
        privateDirectory: private,
        stagingDirectory: staging,
      );

      final staged = await store.stage(
        fileId: 'file-a',
        owner: 'JourneyArtifact',
        sourcePath: source.path,
        purpose: 'submission',
        sensitivity: 'private',
      );

      expect(staged.path, startsWith(staging.path));
      expect(await File(staged.path).readAsString(), 'private payload');

      final otherProfile = ProfileFileStore(
        database: database,
        profileId: 'profile-b',
        privateDirectory: Directory('${root.path}/profile-b/files'),
        stagingDirectory: Directory('${root.path}/profile-b/staging'),
      );
      expect(await otherProfile.read('file-a'), isNull);

      final promoted = await store.promoteToPrivate('file-a');
      expect(promoted.path, startsWith(private.path));
      expect(await File(promoted.path).readAsString(), 'private payload');
      expect(File(staged.path).existsSync(), isFalse);
    },
  );

  test(
    'owner confirmation promotes staging without owning the endpoint',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-transfer-');
      final database = MakoloDatabase.memory();
      addTearDown(() async {
        await database.close();
        await root.delete(recursive: true);
      });

      final source = File('${root.path}/capture.jpg');
      await source.writeAsBytes([1, 2, 3, 4]);
      final store = ProfileFileStore(
        database: database,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      );
      await store.stage(
        fileId: 'capture-a',
        owner: 'Proof',
        sourcePath: source.path,
        purpose: 'proof-capture',
        sensitivity: 'private',
      );

      final owner = ConfirmingOwnerTransfer();
      final receipt = await FileTransferCoordinator(store)
          .uploadToOwner(fileId: 'capture-a', owner: owner);

      expect(receipt.confirmed, isTrue);
      expect(receipt.remoteVersion, 'server-version-1');
      expect(owner.uploaded?.owner, 'Proof');
      expect((await store.read('capture-a'))?.path, contains('/private/'));
    },
  );

  test(
    'reconstructible media cache commits atomically and reuses bytes',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-media-');
      addTearDown(() => root.delete(recursive: true));
      final cache = ProfileMediaCache(profileId: 'profile-a', directory: root);
      var downloads = 0;

      final first = await cache.getOrDownload(
        'owner/resource/version-1',
        extension: 'jpg',
        download: (destinationPath, cancel, onProgress) async {
          downloads += 1;
          final file = File(destinationPath);
          await file.writeAsBytes([4, 3, 2, 1]);
          onProgress?.call(4, 4);
        },
      );
      final second = await cache.getOrDownload(
        'owner/resource/version-1',
        extension: 'jpg',
        download: (destinationPath, cancel, onProgress) async {
          downloads += 1;
        },
      );

      expect(first.path, second.path);
      expect(await first.readAsBytes(), [4, 3, 2, 1]);
      expect(downloads, 1);

      await cache.purge();
      expect(await cache.cached('owner/resource/version-1'), isNull);
    },
  );
}
