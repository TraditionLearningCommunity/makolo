import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

void main() {
  test(
    'staging cleanup removes only explicitly approved Profile files',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-cleanup-');
      final database = MakoloDatabase.memory();
      addTearDown(() async {
        await database.close();
        await root.delete(recursive: true);
      });
      final store = ProfileFileStore(
        database: database,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      );
      final firstSource = File('${root.path}/first.tmp');
      final secondSource = File('${root.path}/second.tmp');
      await firstSource.writeAsBytes([1]);
      await secondSource.writeAsBytes([2]);
      await store.stage(
        fileId: 'remove-me',
        owner: 'InboundCapture',
        sourcePath: firstSource.path,
        purpose: 'share',
        sensitivity: 'private',
      );
      await store.stage(
        fileId: 'keep-me',
        owner: 'Proof',
        sourcePath: secondSource.path,
        purpose: 'submission',
        sensitivity: 'private',
      );

      final removed = await store.cleanupStaging(
        canRemove: (file) => file.owner == 'InboundCapture',
      );

      expect(removed, 1);
      expect(await store.read('remove-me'), isNull);
      expect(await store.read('keep-me'), isNotNull);
    },
  );
  test(
    'cleanup keeps staged files required by a draft or unresolved outbox',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-safe-gc-');
      final db = MakoloDatabase.memory();
      addTearDown(() async {
        await db.close();
        await root.delete(recursive: true);
      });
      final fileStore = ProfileFileStore(
        database: db,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      );
      final source = File('${root.path}/original.pdf');
      await source.writeAsBytes([1, 2, 3]);
      for (final id in ['draft-file', 'outbox-file', 'orphan']) {
        await fileStore.stage(
          fileId: id,
          owner: 'JourneyArtifact',
          sourcePath: source.path,
          purpose: 'preparation',
          sensitivity: 'private',
        );
      }
      final outbox = OutboxRepository(db, 'profile-a');
      final drafts = DraftRepository(
        database: db,
        outbox: outbox,
        profileId: 'profile-a',
      );
      await drafts.saveLocal(
        draftId: 'prepared-document',
        owner: 'JourneyArtifact',
        resourceKind: 'journey_artifact',
        payload: {
          'attachment': {'file_id': 'draft-file'},
        },
      );
      await outbox.enqueue(
        operationId: 'upload-operation',
        deviceInstanceId: 'device-a',
        operationKind: 'journey.upload',
        owner: 'JourneyArtifact',
        payload: {
          'files': ['outbox-file'],
        },
        intentId: 'upload-intent',
        replayPolicy: ReplayPolicy.refetchBeforeRetry,
      );
      expect(await fileStore.cleanupStaging(canRemove: (_) => true), 1);
      expect(await fileStore.read('draft-file'), isNotNull);
      expect(await fileStore.read('outbox-file'), isNotNull);
      expect(await fileStore.read('orphan'), isNull);
    },
  );

  test(
    'a duplicate FileRecord never destroys existing bytes or crosses Profile',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-file-ids-');
      final db = MakoloDatabase.memory();
      addTearDown(() async {
        await db.close();
        await root.delete(recursive: true);
      });
      ProfileFileStore store(String profile) => ProfileFileStore(
        database: db,
        profileId: profile,
        privateDirectory: Directory('${root.path}/$profile/private'),
        stagingDirectory: Directory('${root.path}/$profile/staging'),
      );
      final original = File('${root.path}/original.txt');
      await original.writeAsString('untouched');
      final first = await store('profile-a').stage(
        fileId: 'unique-owner-file',
        owner: 'Proof',
        sourcePath: original.path,
        purpose: 'document',
        sensitivity: 'private',
      );
      await original.writeAsString('replacement');
      await expectLater(
        store('profile-a').stage(
          fileId: 'unique-owner-file',
          owner: 'Proof',
          sourcePath: original.path,
          purpose: 'document',
          sensitivity: 'private',
        ),
        throwsStateError,
      );
      await expectLater(
        store('profile-b').stage(
          fileId: 'unique-owner-file',
          owner: 'Proof',
          sourcePath: original.path,
          purpose: 'document',
          sensitivity: 'private',
        ),
        throwsStateError,
      );
      expect(await File(first.path).readAsString(), 'untouched');
      expect(await store('profile-b').read('unique-owner-file'), isNull);
      expect(await File(first.path).exists(), isTrue);
    },
  );

  test('a partial capture never appears as an acquired FileRecord', () async {
    final root = await Directory.systemTemp.createTemp('makolo-partial-');
    final db = MakoloDatabase.memory();
    addTearDown(() async {
      await db.close();
      await root.delete(recursive: true);
    });
    final staging = Directory('${root.path}/staging');
    final store = ProfileFileStore(
      database: db,
      profileId: 'profile-a',
      privateDirectory: Directory('${root.path}/private'),
      stagingDirectory: staging,
    );
    await expectLater(
      store.stageCopy(
        fileId: 'interrupted',
        owner: 'InboundCapture',
        sourceFilename: 'private.pdf',
        purpose: 'capture',
        sensitivity: 'private',
        writeTo: (path) async {
          await File(path).writeAsBytes([1, 2]);
          throw StateError('process interrupted');
        },
      ),
      throwsStateError,
    );
    expect(await store.read('interrupted'), isNull);
    expect(await staging.list().toList(), isEmpty);
  });

  test(
    'restart maintenance removes old orphan parts, not tracked staging',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-orphans-');
      final db = MakoloDatabase.memory();
      addTearDown(() async {
        await db.close();
        await root.delete(recursive: true);
      });
      final store = ProfileFileStore(
        database: db,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      );
      final source = File('${root.path}/source.pdf');
      await source.writeAsBytes([4, 5]);
      final tracked = await store.stage(
        fileId: 'kept-intent',
        owner: 'JourneyArtifact',
        sourcePath: source.path,
        purpose: 'submit',
        sensitivity: 'private',
      );
      final orphan = File('${store.stagingDirectory.path}/stage-crashed.part');
      await orphan.writeAsBytes([1]);
      final old = DateTime.now().subtract(const Duration(days: 4));
      await orphan.setLastModified(old);
      await File(tracked.path).setLastModified(old);
      expect(await store.cleanupInterruptedStaging(), 1);
      expect(await orphan.exists(), isFalse);
      expect(await File(tracked.path).exists(), isTrue);
      expect((await store.read('kept-intent'))?.path, tracked.path);
    },
  );

  test(
    'private promotion is idempotent and survives a fresh FileStore',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-restart-');
      final db = MakoloDatabase.memory();
      addTearDown(() async {
        await db.close();
        await root.delete(recursive: true);
      });
      ProfileFileStore store() => ProfileFileStore(
        database: db,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      );
      final source = File('${root.path}/source.pdf');
      await source.writeAsBytes([6, 7, 8]);
      final staged = await store().stage(
        fileId: 'file-1',
        owner: 'Resource',
        sourcePath: source.path,
        purpose: 'offline-use',
        sensitivity: 'private',
      );
      expect(await File(staged.path).exists(), isTrue);
      final promoted = await store().promoteToPrivate('file-1');
      final second = await store().promoteToPrivate('file-1');
      expect(second.path, promoted.path);
      expect(await File(promoted.path).readAsBytes(), [6, 7, 8]);
      expect(await File(staged.path).exists(), isFalse);
    },
  );
}
