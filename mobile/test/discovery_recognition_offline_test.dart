import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_offline_store.dart';

void main() {
  test('public card bytes survive cache purge but are not an explicit save', (
    ) async {
    final root = await Directory.systemTemp.createTemp('makolo-public-media-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root);
    final uri = Uri.parse(
      'https://makolo.example/presentation/media/public/photo.jpg',
    );
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

  test('automatic Discovery images rotate at ten without deleting Reader files', (
    ) async {
    final root = await Directory.systemTemp.createTemp('makolo-budget-test-');
    addTearDown(() async => root.delete(recursive: true));
    final store = DiscoveryOfflineStore(rootOverride: root);
    final savedUrl = Uri.parse('https://makolo.example/manual.pdf');
    final source = File('${root.path}/manual.pdf');
    await source.writeAsBytes([1, 2, 3]);
    await store.save(savedUrl, source);

    for (var i = 0; i < 13; i++) {
      await store.retainRecognitionImage(
        Uri.parse('https://makolo.example/image/$i'),
        Uint8List.fromList([i + 1]),
      );
      await Future<void>.delayed(const Duration(milliseconds: 3));
    }
    var retained = 0;
    for (var i = 0; i < 13; i++) {
      if (await store.recognizedImage(
        Uri.parse('https://makolo.example/image/$i'),
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
    final store = DiscoveryOfflineStore(rootOverride: root);
    final uri = Uri.parse('https://makolo.example/published/document.png');
    final source = File('${root.path}/image.png');
    await source.writeAsBytes([1, 2, 3, 4]);
    await store.save(uri, source);
    await store.retainRecognitionImage(uri, Uint8List.fromList([7, 8, 9]));
    await store.removeRecognitionImage(uri);
    expect(await store.recognizedImage(uri), isNull);
    expect(await store.retained(uri), isNotNull);
  });
}
