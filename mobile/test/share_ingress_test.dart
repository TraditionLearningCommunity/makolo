import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/platform/sharing/shared_payload_coordinator.dart';
import 'package:makolo_mobile/platform/sharing/system_share_receiver.dart';

void main() {
  test('shared file is immediately copied into Profile staging', () async {
    final root = await Directory.systemTemp.createTemp('makolo-share-');
    final database = MakoloDatabase.memory();
    addTearDown(() async {
      await database.close();
      await root.delete(recursive: true);
    });
    final staging = Directory('${root.path}/profile-a/staging');
    final store = ProfileFileStore(
      database: database,
      profileId: 'profile-a',
      privateDirectory: Directory('${root.path}/profile-a/private'),
      stagingDirectory: staging,
    );
    final payload = SharedPayload(
      kind: SharedPayloadKind.files,
      files: [
        SharedFileReference(
          uri: 'content://provider/private',
          name: 'passport.pdf',
          mimeType: 'application/pdf',
          copyTo: (destinationPath) =>
              File(destinationPath).writeAsBytes([9, 8, 7]),
        ),
      ],
    );

    final capture = await SharedPayloadCoordinator(store)
        .capture(payload, fileIdFor: (_, _) => 'opaque-capture-1');

    expect(capture.files.single.owner, 'InboundCapture');
    expect(capture.files.single.path, startsWith(staging.path));
    expect(capture.files.single.path, isNot(contains('passport')));
    expect(await File(capture.files.single.path).readAsBytes(), [9, 8, 7]);
  });

  test(
    'shared text remains technical input and creates no file record',
    () async {
      final root = await Directory.systemTemp.createTemp('makolo-share-text-');
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

      final capture = await SharedPayloadCoordinator(store).capture(
        const SharedPayload(
          kind: SharedPayloadKind.text,
          text: 'Préparer ce document',
        ),
        fileIdFor: (_, __) => 'unused',
      );

      expect(capture.text, 'Préparer ce document');
      expect(await store.stagedFiles(), isEmpty);
    },
  );
}
