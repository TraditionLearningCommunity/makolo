import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_offline_store.dart';

void main() {
  test('an open Reader invalidates retained bytes on Profile switch', () {
    final code = File('lib/presentation/possibilities/discovery_reader.dart')
        .readAsStringSync();
    expect(code, contains('oldWidget.profileId != widget.profileId'));
    expect(code, contains('_generation++'));
    expect(code, contains('_retainedFile = null'));
    expect(code, contains('_imageBytes = null'));
  });

  test(
    'explicit Reader files are Profile private, not device-global',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'discover-local-reader-',
      );
      addTearDown(() => root.delete(recursive: true));
      final a = DiscoveryOfflineStore(
        rootOverride: root,
        profileId: 'profile-a',
      );
      final b = DiscoveryOfflineStore(
        rootOverride: root,
        profileId: 'profile-b',
      );
      final url = Uri.parse('https://example.test/documents/report.pdf');
      final source = File('${root.path}/source.pdf');
      await source.writeAsBytes([0x25, 0x50, 0x44, 0x46], flush: true);

      await a.save(url, source);
      expect(await a.retained(url), isNotNull);
      expect(await b.retained(url), isNull);
      expect(
        (await a.location(url)).path,
        contains('/profiles/profile-a/discovery/reader/'),
      );
      expect(
        (await b.location(url)).path,
        contains('/profiles/profile-b/discovery/reader/'),
      );

      await a.purgePrivateReader();
      expect(await a.retained(url), isNull);
      await b.save(url, source);
      expect(await b.retained(url), isNotNull);
      await a.purgePrivateReader();
      expect(await b.retained(url), isNotNull);
    },
  );

  test(
    'old shared Reader paths are not read after the privacy correction',
    () async {
      final root = await Directory.systemTemp.createTemp('discover-legacy-');
      addTearDown(() => root.delete(recursive: true));
      final url = Uri.parse('https://example.test/document/secret.pdf');
      final legacy = Directory('${root.path}/discovery/public-offline');
      await legacy.create(recursive: true);
      await File('${legacy.path}/${DiscoveryOfflineStore.keyFor(url)}.data')
          .writeAsString('old shared private bytes');

      final a = DiscoveryOfflineStore(
        rootOverride: root,
        profileId: 'profile-a',
      );
      final guest = DiscoveryOfflineStore(rootOverride: root);
      expect(await a.retained(url), isNull);
      expect(await legacy.exists(), isFalse);
      expect(await guest.retained(url), isNull);
      await expectLater(guest.location(url), throwsA(isA<FormatException>()));
    },
  );

  test(
    'guest retention is restricted to published first-party media',
    () async {
      final root = await Directory.systemTemp.createTemp('discover-public-');
      addTearDown(() => root.delete(recursive: true));
      final origin = Uri.parse('https://makolo.invalid/');
      final guest = DiscoveryOfflineStore(
        rootOverride: root,
        trustedOrigin: origin,
      );
      final published = Uri.parse(
        'https://makolo.invalid/presentation/media/uses/'
        '11111111-2222-3333-4444-555555555555/file/',
      );
      final external = Uri.parse('https://external.test/secret.pdf');
      final tokenized = published.replace(queryParameters: {'token': 'secret'});
      expect(await guest.retained(external), isNull);
      expect(await guest.retained(tokenized), isNull);

      final source = File('${root.path}/photo.bin');
      await source.writeAsBytes([1, 2, 3]);
      await expectLater(
        guest.save(external, source),
        throwsA(isA<FormatException>()),
      );
      await guest.save(published, source);
      expect(await guest.retained(published), isNotNull);
      expect(await guest.retained(tokenized), isNull);
    },
  );

  test(
    'Profile Reader rejects signed and credentialed URLs for persistence',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'discover-private-url-',
      );
      addTearDown(() => root.delete(recursive: true));
      final privateStore = DiscoveryOfflineStore(
        rootOverride: root,
        profileId: 'profile-a',
      );
      final source = File('${root.path}/source.pdf');
      await source.writeAsBytes([37, 80, 68, 70]);
      for (final uri in [
        Uri.parse('https://owner.test/file.pdf?token=secret'),
        Uri.parse('https://owner.test/file.pdf#fragment'),
        Uri.parse('https://person:password@owner.test/file.pdf'),
        Uri.parse('file:///tmp/secret.pdf'),
      ]) {
        expect(await privateStore.retained(uri), isNull);
        await expectLater(
          privateStore.save(uri, source),
          throwsA(isA<FormatException>()),
        );
      }
    },
  );

  test(
    'public automatic recognition revocation does not remove Reader files',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'discover-media-revoke-',
      );
      addTearDown(() => root.delete(recursive: true));
      final origin = Uri.parse('https://makolo.invalid/');
      final store = DiscoveryOfflineStore(
        rootOverride: root,
        trustedOrigin: origin,
        profileId: 'profile-a',
      );
      final uri = Uri.parse(
        'https://makolo.invalid/presentation/media/uses/'
        '11111111-2222-3333-4444-555555555555/file/',
      );
      await store.retainRecognitionImage(uri, Uint8List.fromList([1, 2, 3]));
      expect(await store.recognizedImage(uri), isNotNull);
      final readerSource = File('${root.path}/manual.pdf');
      await readerSource.writeAsBytes([3, 2, 1]);
      final pdf = Uri.parse('https://external.test/manual.pdf');
      await store.save(pdf, readerSource);
      await store.purgeAutomaticRecognition();
      expect(await store.recognizedImage(uri), isNull);
      expect(await store.retained(pdf), isNotNull);
      await store.purgePrivateReader();
      expect(await store.retained(pdf), isNull);
    },
  );
}
