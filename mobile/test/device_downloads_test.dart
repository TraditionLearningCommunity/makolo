import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/downloads/device_downloads.dart';

void main() {
  test('download filenames preserve a safe extension and strip path syntax', () {
    expect(
      makoloDownloadName('Guide / documents : Kolwezi', 'pdf'),
      'Guide - documents - Kolwezi.pdf',
    );
    expect(
      makoloDownloadName('  Image documentaire  ', 'png'),
      'Image documentaire.png',
    );
    expect(
      makoloDownloadName('..', 'txt'),
      'Document Makolo.txt',
    );
    expect(
      makoloDownloadName('Fichier', 'JPG'),
      'Fichier.jpg',
    );
  });
}
