import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_recognition_image_store.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/presentation/media/retained_recognition_image.dart';

class _RecognitionApi implements MakoloApiClient {
  _RecognitionApi(this.fetch);

  final Future<Uint8List> Function(String path) fetch;

  @override
  Future<Uint8List> getPresentationImage(String path) => fetch(path);

  @override
  dynamic noSuchMethod(Invocation invocation) =>
      super.noSuchMethod(invocation);
}

void main() {
  const imagePath = '/presentation/media/uses/published/image/';
  final imageBytes = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
    'AAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==',
  );

  late Directory supportRoot;

  setUp(() async {
    supportRoot = await Directory.systemTemp.createTemp(
      'makolo-recognition-test-',
    );
  });

  tearDown(() async {
    if (await supportRoot.exists()) {
      await supportRoot.delete(recursive: true);
    }
  });

  test('published recognition bytes survive a cache purge and restart', () async {
    const profile = 'profile-a';
    final store = ProfileRecognitionImageStore(
      profileId: profile,
      rootOverride: supportRoot,
    );
    await store.save(imagePath, imageBytes);

    final reconstructible = Directory('${supportRoot.path}/cache');
    await reconstructible.create(recursive: true);
    await File('${reconstructible.path}/unused.tmp').writeAsString('cache');
    await reconstructible.delete(recursive: true);

    final restarted = ProfileRecognitionImageStore(
      profileId: profile,
      rootOverride: supportRoot,
    );
    expect(await restarted.read(imagePath), orderedEquals(imageBytes));
  });

  test('one Profile cannot read a second Profile recognition copy', () async {
    final a = ProfileRecognitionImageStore(
      profileId: 'profile-a',
      rootOverride: supportRoot,
    );
    final b = ProfileRecognitionImageStore(
      profileId: 'profile-b',
      rootOverride: supportRoot,
    );
    await a.save(imagePath, imageBytes);
    expect(await b.read(imagePath), isNull);
    expect(await a.read(imagePath), orderedEquals(imageBytes));
    await a.remove(imagePath);
    expect(await a.read(imagePath), isNull);
  });

  test('empty recognition bytes cannot overwrite a durable file', () async {
    final store = ProfileRecognitionImageStore(
      profileId: 'profile-a',
      rootOverride: supportRoot,
    );
    await store.save(imagePath, imageBytes);
    await expectLater(
      store.save(imagePath, Uint8List(0)),
      throwsA(isA<FormatException>()),
    );
    expect(await store.read(imagePath), orderedEquals(imageBytes));
  });

  testWidgets('transport failure shows retained media without an offline page', (
    tester,
  ) async {
    final store = ProfileRecognitionImageStore(
      profileId: 'profile-a',
      rootOverride: supportRoot,
    );
    await store.save(imagePath, imageBytes);
    final api = _RecognitionApi(
      (_) async => throw const MakoloTransportError(
        'offline',
        'unreachable',
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: RetainedRecognitionImage(
          api: api,
          profileId: 'profile-a',
          path: imagePath,
          alt: 'Photo publiée',
          storeOverride: store,
          placeholder: const Icon(Icons.image_not_supported_outlined),
        ),
      ),
    );
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 30));
    });
    await tester.pump();
    expect(find.byType(Image), findsOneWidget);
    expect(await store.read(imagePath), orderedEquals(imageBytes));
  });

  testWidgets('owner 403 revokes the local recognition copy', (tester) async {
    final store = ProfileRecognitionImageStore(
      profileId: 'profile-a',
      rootOverride: supportRoot,
    );
    await store.save(imagePath, imageBytes);
    final api = _RecognitionApi(
      (_) async => throw const MakoloApiError(
        statusCode: 403,
        code: 'permission_denied',
        message: 'revoked',
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: RetainedRecognitionImage(
          api: api,
          profileId: 'profile-a',
          path: imagePath,
          alt: 'Photo publiée',
          storeOverride: store,
          placeholder: const Icon(Icons.image_not_supported_outlined),
        ),
      ),
    );
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 30));
    });
    await tester.pump();
    expect(await store.read(imagePath), isNull);
    expect(find.byType(Image), findsNothing);
  });
}
