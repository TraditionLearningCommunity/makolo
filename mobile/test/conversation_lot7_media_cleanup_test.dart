import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/conversation_attachment_viewer.dart';

Future<void> expectPrivateFileDeleted(File file) async {
  for (var attempt = 0; attempt < 30; attempt++) {
    if (!await file.exists()) return;
    await Future<void>.delayed(const Duration(milliseconds: 15));
  }
  expect(await file.exists(), isFalse);
}

void main() {
  testWidgets('Lot 7: gallery navigation discards stale private downloads', (
    tester,
  ) async {
    final directory = await Directory.systemTemp.createTemp('makolo-lot7-');
    addTearDown(() => directory.delete(recursive: true));
    final firstFile = await File('${directory.path}/first.bin').writeAsBytes([1, 2]);
    final nextFile = await File('${directory.path}/next.bin').writeAsBytes([3, 4]);
    final first = Completer<File>();
    final next = Completer<File>();

    await tester.pumpWidget(
      MaterialApp(
        home: ConversationAttachmentViewer(
          attachment: const {'id': 'first', 'name': 'first.bin', 'kind': 'file'},
          gallery: const [
            {'id': 'first', 'name': 'first.bin', 'kind': 'file'},
            {'id': 'next', 'name': 'next.bin', 'kind': 'file'},
          ],
          download: ({
            required String attachmentId,
            required String filename,
          }) => attachmentId == 'first' ? first.future : next.future,
        ),
      ),
    );

    await tester.tap(find.byTooltip('Média suivant'));
    await tester.pump();
    first.complete(firstFile);
    await tester.pump();

    await tester.runAsync(() => expectPrivateFileDeleted(firstFile));
    // The second download is still loading when the gallery disappears.
    await tester.pumpWidget(const SizedBox.shrink());
    next.complete(nextFile);
    await tester.pump();
    await tester.runAsync(() => expectPrivateFileDeleted(nextFile));
  });

  testWidgets('Lot 7: closing the private document reader deletes its file', (
    tester,
  ) async {
    final directory = await Directory.systemTemp.createTemp('makolo-lot7-reader-');
    addTearDown(() => directory.delete(recursive: true));
    final file = await File('${directory.path}/private.bin').writeAsBytes([5, 6]);

    await tester.pumpWidget(
      MaterialApp(
        home: ConversationAttachmentViewer(
          attachment: const {
            'id': 'private',
            'name': 'private.bin',
            'kind': 'file',
            'mime_type': 'application/octet-stream',
          },
          download: ({
            required String attachmentId,
            required String filename,
          }) async => file,
        ),
      ),
    );
    await tester.pump();
    expect(await file.exists(), isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.runAsync(() => expectPrivateFileDeleted(file));
  });
}
