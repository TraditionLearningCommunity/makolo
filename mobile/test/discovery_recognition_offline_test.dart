import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_offline_store.dart';

Uri publicUse(int n) => Uri.parse(
  'https://makolo.example/presentation/media/uses/'
  '00000000-0000-4000-8000-${n.toString().padLeft(12, '0')}/file/',
);

void main() {
  test('automatic retention rejects first-party nonpublic URLs', () async {
    final root = await Directory.systemTemp.createTemp('makolo-reject-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root, trustedOrigin: Uri.parse('https://makolo.example'));
    final privateUri = Uri.parse('https://makolo.example/api/v1/me/private.jpg');
    expect(
      () => store.retainRecognitionImage(privateUri, Uint8List.fromList([1])),
      throwsFormatException,
    );
    expect(await store.recognizedImage(privateUri), isNull);
  });

  test('public card bytes survive cache purge but are not an explicit save', (
    ) async {
    final root = await Directory.systemTemp.createTemp('makolo-public-media-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root, trustedOrigin: Uri.parse('https://makolo.example'));
    final uri = publicUse(1);
    final bytes = Uint8List.fromList([0xff, 0xd8, 0xff, 0xd9]);
    await store.retainRecognitionImage(uri, bytes);

    final cache = Directory('${root.path}/cache');
    await cache.create();
    await File('${cache.path}/reconstructible').writeAsString('temp');
    await cache.delete(recursive: true);

    expect(await store.recognizedImage(uri), orderedEquals(bytes));
    expect(await store.retained(uri), isNull);
    await store.removeRecognitionImage(uri);
    expect(await store.recognizedImage(uri), isNull);
  });

  test('parallel public recognition writes keep the final complete bytes', () async {
    final root = await Directory.systemTemp.createTemp('makolo-concurrent-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root, trustedOrigin: Uri.parse('https://makolo.example'));
    final url = publicUse(9);
    await Future.wait([
      store.retainRecognitionImage(url, Uint8List.fromList([1])),
      store.retainRecognitionImage(url, Uint8List.fromList([2])),
    ]);
    expect(await store.recognizedImage(url), orderedEquals([2]));
  });

  test('automatic Discovery images rotate at ten without deleting Reader files', (
    ) async {
    final root = await Directory.systemTemp.createTemp('makolo-budget-test-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root, trustedOrigin: Uri.parse('https://makolo.example'));
    final savedUrl = Uri.parse('https://makolo.example/manual.pdf');
    final source = File('${root.path}/manual.pdf');
    await source.writeAsBytes([1, 2, 3]);
    await store.save(savedUrl, source);

    for (var i = 0; i < 13; i++) {
      await store.retainRecognitionImage(
        publicUse(i + 1),
        Uint8List.fromList([i + 1]),
      );
      await Future<void>.delayed(const Duration(milliseconds: 3));
    }
    var retained = 0;
    for (var i = 0; i < 13; i++) {
      if (await store.recognizedImage(
        publicUse(i + 1),
      ) != null) {
        retained++;
      }
    }
    expect(retained, DiscoveryOfflineStore.maxAutomaticImages);
    expect(await store.retained(savedUrl), isNotNull);
  });

  test('manual Reader retention is independent of automatic card bytes', (
    ) async {
    final root = await Directory.systemTemp.createTemp('makolo-reader-media-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root, trustedOrigin: Uri.parse('https://makolo.example'));
    final uri = publicUse(3);
    final source = File('${root.path}/image.png');
    await source.writeAsBytes([1, 2, 3, 4]);
    await store.save(uri, source);
    await store.retainRecognitionImage(uri, Uint8List.fromList([7, 8, 9]));
    await store.removeRecognitionImage(uri);
    expect(await store.recognizedImage(uri), isNull);
    expect(await store.retained(uri), isNotNull);
  });
  test('identical published path on a foreign origin is not trusted', () async {
    final root = await Directory.systemTemp.createTemp('makolo-foreign-media-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(
      rootOverride: root,
      trustedOrigin: Uri.parse('https://makolo.example'),
    );
    final forged = Uri.parse(
      'https://attacker.example/presentation/media/uses/'
      '00000000-0000-4000-8000-000000000001/file/',
    );
    expect(
      DiscoveryOfflineStore.isPublishedRecognitionUri(
        forged,
        trustedOrigin: Uri.parse('https://makolo.example'),
      ),
      isFalse,
    );
    await expectLater(
      store.retainRecognitionImage(forged, Uint8List.fromList([1])),
      throwsFormatException,
    );
    expect(await store.recognizedImage(forged), isNull);
    expect(
      DiscoveryOfflineStore.isPublishedRecognitionUri(publicUse(1)),
      isFalse,
    );
  });

  test('replacing retained image leaves one complete copy, not staging data', () async {
    final root = await Directory.systemTemp.createTemp('makolo-replace-media-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(
      rootOverride: root,
      trustedOrigin: Uri.parse('https://makolo.example'),
    );
    final uri = publicUse(19);
    await store.retainRecognitionImage(uri, Uint8List.fromList([1, 2, 3]));
    await store.retainRecognitionImage(uri, Uint8List.fromList([4, 5]));
    expect(await store.recognizedImage(uri), orderedEquals([4, 5]));
    final retained = Directory('${root.path}/discovery/public-recognition');
    final entries = await retained.list().toList();
    expect(entries.whereType<File>().length, 1);
    expect(entries.single.path.endsWith('.image'), isTrue);
  });

}
