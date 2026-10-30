import 'dart:io';

import 'package:flutter/services.dart';

/// Direct public Downloads export. Separate from Sharing and from the private
/// profile-local offline cache. The caller must already own authorized bytes.
abstract interface class DeviceDownloads {
  Future<String> save({
    required File source,
    required String fileName,
    required String mimeType,
  });
}

class AndroidDeviceDownloads implements DeviceDownloads {
  const AndroidDeviceDownloads();

  static const MethodChannel _channel = MethodChannel('makolo/downloads');

  @override
  Future<String> save({
    required File source,
    required String fileName,
    required String mimeType,
  }) async {
    if (!Platform.isAndroid) {
      throw UnsupportedError(
        'Le téléchargement direct est actuellement disponible sur Android.',
      );
    }
    if (fileName.isEmpty ||
        fileName == '.' ||
        fileName == '..' ||
        fileName.contains('/') ||
        fileName.contains('\\') ||
        fileName.codeUnits.any((c) => c < 32)) {
      throw const FormatException('Nom de fichier non autorisé.');
    }
    if (!await source.exists() || await source.length() == 0) {
      throw const FileSystemException('Fichier indisponible.');
    }
    final saved = await _channel.invokeMethod<String>('saveFile', {
      'source_path': source.path,
      'file_name': fileName,
      'mime_type': mimeType,
    });
    if (saved == null || saved.isEmpty) {
      throw const FileSystemException('Enregistrement non confirmé.');
    }
    return saved;
  }
}

/// Human-readable export name, without trusting server filenames or URL paths.
String makoloDownloadName(String title, String extension) {
  final safeTitle = title
      .trim()
      .replaceAll(RegExp(r'[\/:*?"<>|\x00-\x1f\\]'), '-')
      .replaceAll(RegExp(r'\s+'), ' ')
      .replaceAll(RegExp(r'^[. ]+|[. ]+$'), '');
  final stem = safeTitle.isEmpty ? 'Document Makolo' : safeTitle;
  final bounded = stem.length > 90 ? stem.substring(0, 90).trimRight() : stem;
  final cleanExtension = extension.toLowerCase().replaceAll(
    RegExp(r'[^a-z0-9]'), '',
  );
  return '$bounded.${cleanExtension.isEmpty ? 'bin' : cleanExtension}';
}
