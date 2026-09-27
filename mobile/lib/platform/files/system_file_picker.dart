import 'dart:io';

import 'package:file_picker/file_picker.dart';

class PickedSystemFile {
  PickedSystemFile({
    required this.name,
    required this.byteLength,
    required Future<void> Function(String destinationPath) copyTo,
  }) : _copyTo = copyTo;

  final String name;
  final int? byteLength;
  final Future<void> Function(String destinationPath) _copyTo;

  Future<void> copyTo(String destinationPath) => _copyTo(destinationPath);
}

abstract interface class SystemFilePicker {
  Future<List<PickedSystemFile>> pick({List<String>? allowedExtensions});
}

class NativeSystemFilePicker implements SystemFilePicker {
  const NativeSystemFilePicker();

  @override
  Future<List<PickedSystemFile>> pick({List<String>? allowedExtensions}) async {
    final files = await FilePicker.pickFiles(
      type: allowedExtensions == null ? FileType.any : FileType.custom,
      allowedExtensions: allowedExtensions,
    );
    final results = <PickedSystemFile>[];
    for (final file in files) {
      final length = file.lengthSync() ?? await file.length();
      results.add(
        PickedSystemFile(
          name: file.name,
          byteLength: length,
          copyTo: (destinationPath) => _copy(file, destinationPath),
        ),
      );
    }
    return results;
  }

  Future<void> _copy(PlatformFile source, String destinationPath) async {
    final destination = File(destinationPath);
    await destination.parent.create(recursive: true);
    final sink = destination.openWrite();
    try {
      await for (final chunk in source.readAsByteStream()) {
        sink.add(chunk);
      }
    } finally {
      await sink.close();
    }
  }
}
