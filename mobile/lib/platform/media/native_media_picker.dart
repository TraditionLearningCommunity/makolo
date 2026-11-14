import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';

/// Native file/camera operations belong to the platform, never feature UI.
/// Only the selected file's path and name cross into the business workflow.
class NativeSelectedMedia {
  const NativeSelectedMedia({required this.path, required this.name});
  final String? path;
  final String name;
}

abstract final class NativeMediaPicker {
  static Future<NativeSelectedMedia?> pickImage({
    required bool camera,
    int quality = 90,
    double maxWidth = 2200,
  }) async {
    final picked = await ImagePicker().pickImage(
      source: camera ? ImageSource.camera : ImageSource.gallery,
      imageQuality: quality,
      maxWidth: maxWidth,
    );
    return picked == null
        ? null
        : NativeSelectedMedia(path: picked.path, name: picked.name);
  }

  static Future<NativeSelectedMedia?> pickDocument(
    List<String> extensions,
  ) async {
    final selected = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: extensions,
    );
    return selected == null
        ? null
        : NativeSelectedMedia(path: selected.path, name: selected.name);
  }
}
