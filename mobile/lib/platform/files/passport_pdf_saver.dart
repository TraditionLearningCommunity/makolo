import 'dart:io';

import 'package:file_picker/file_picker.dart';

Future<Uri?> savePassportPdf(String path, String filename) async {
  return FilePicker.saveFile(
    dialogTitle: 'Enregistrer le Passeport PDF',
    fileName: filename,
    type: FileType.custom,
    allowedExtensions: const ['pdf'],
    bytes: await File(path).readAsBytes(),
  );
}
