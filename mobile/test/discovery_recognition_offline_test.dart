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
