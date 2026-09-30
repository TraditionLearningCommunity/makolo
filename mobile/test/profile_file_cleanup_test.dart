import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';

void main() {
  test('staging cleanup removes only explicitly approved Profile files', () async {
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
  });
}
