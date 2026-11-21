import 'dart:async';
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
  test(
    'concurrent media requests share one completed private cache file',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-cache-c5-');
      addTearDown(() => root.delete(recursive: true));
      final cache = ProfileMediaCache(profileId: 'profile-a', directory: root);
      final firstStarted = Completer<void>();
      final finish = Completer<void>();
      var downloads = 0;

      Future<void> download(
        String path,
        dynamic cancel,
        dynamic progress,
      ) async {
        downloads++;
        if (!firstStarted.isCompleted) firstStarted.complete();
        await finish.future;
        await File(path).writeAsBytes([9, 8, 7], flush: true);
      }

      final first = cache.getOrDownload(
        'one-image',
        extension: 'jpg',
        download: download,
      );
      await firstStarted.future;
      final second = cache.getOrDownload(
        'one-image',
        extension: 'jpg',
        download: download,
      );
      finish.complete();
      final results = await Future.wait([first, second]);
      expect(downloads, 1);
      expect(results[0].path, results[1].path);
      expect(await results[0].readAsBytes(), [9, 8, 7]);
    },
  );

  test(
    'media failure removes part and never publishes partial bytes',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-cache-fail-');
      addTearDown(() => root.delete(recursive: true));
      final cache = ProfileMediaCache(profileId: 'profile-a', directory: root);
      await expectLater(
        cache.getOrDownload(
          'failed-media',
          extension: 'jpg',
          download: (path, _, _) async {
            await File(path).writeAsBytes([1, 2]);
            throw const FileSystemException('network ended early');
          },
        ),
        throwsA(isA<FileSystemException>()),
      );
      expect(await cache.cached('failed-media', extension: 'jpg'), isNull);
      expect(await root.list().toList(), isEmpty);
    },
  );

  test(
    'cache purge after an in-flight download cannot restore old bytes',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-cache-purge-');
      addTearDown(() => root.delete(recursive: true));
      final cache = ProfileMediaCache(profileId: 'profile-a', directory: root);
      final started = Completer<void>();
      final finish = Completer<void>();
      final download = cache.getOrDownload(
        'image',
        extension: 'png',
        download: (path, _, _) async {
          started.complete();
          await finish.future;
          await File(path).writeAsBytes([3, 1, 4], flush: true);
        },
      );
      await started.future;
      final purge = cache.purge();
      finish.complete();
      await download;
      await purge;
      expect(await cache.cached('image', extension: 'png'), isNull);
    },
  );

  test(
    'cache evicts oldest reconstructible media, not private files',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'makolo-cache-budget-',
      );
      addTearDown(() => root.delete(recursive: true));
      final cache = ProfileMediaCache(profileId: 'profile-a', directory: root);
      for (
        var index = 0;
        index < ProfileMediaCache.maxCachedFiles + 2;
        index++
      ) {
        await cache.getOrDownload(
          'image-$index',
          extension: 'jpg',
          download: (path, _, _) =>
              File(path).writeAsBytes([index], flush: true),
        );
      }
      expect(
        await root.list().where((e) => e is File).length,
        ProfileMediaCache.maxCachedFiles,
      );
      expect(await cache.cached('image-0', extension: 'jpg'), isNull);
      expect(await cache.cached('image-61', extension: 'jpg'), isNotNull);
    },
  );
}
