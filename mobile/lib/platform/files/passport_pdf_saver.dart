import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/services.dart';

/// Save directly in the public Android Downloads collection. The existing
/// native MediaStore channel handles scoped storage and cleans failed writes.
/// Other platforms retain their user-selected destination (no unsafe
/// assumptions about public filesystem paths).
Future<Uri?> savePassportPdf(String path, String filename) async {
  if (Platform.isAndroid) {
    final savedName = await const MethodChannel('makolo/downloads')
        .invokeMethod<String>('saveFile', {
          'source_path': path,
          'file_name': filename,
          'mime_type': 'application/pdf',
        });
    if (savedName == null || savedName.isEmpty) {
      throw PlatformException(
        code: 'download_failed',
        message: 'Le dossier Téléchargements est indisponible.',
      );
    }
    // The platform owns the MediaStore URI. Do not manufacture a file:// URI
    // for a scoped-storage document; this is only an export success marker.
    return Uri(path: savedName);
  }
  return FilePicker.saveFile(
    dialogTitle: 'Enregistrer le Passeport PDF',
    fileName: filename,
    type: FileType.custom,
    allowedExtensions: const ['pdf'],
    bytes: await File(path).readAsBytes(),
  );
}
