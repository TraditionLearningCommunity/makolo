import 'package:image_picker/image_picker.dart';

enum PickedMediaKind { image, video }

class SystemPickedMedia {
  const SystemPickedMedia({
    required this.path,
    required this.name,
    required this.kind,
    this.mimeType,
  });

  final String path;
  final String name;
  final PickedMediaKind kind;
  final String? mimeType;
}

abstract interface class SystemMediaPicker {
  Future<SystemPickedMedia?> pickImage({bool capture = false});
  Future<SystemPickedMedia?> pickVideo({bool capture = false});
  Future<List<SystemPickedMedia>> recoverInterruptedPick();
}

class ImagePickerSystemMediaPicker implements SystemMediaPicker {
  ImagePickerSystemMediaPicker({ImagePicker? picker})
    : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  @override
  Future<SystemPickedMedia?> pickImage({bool capture = false}) async {
    final file = await _picker.pickImage(
      source: capture ? ImageSource.camera : ImageSource.gallery,
    );
    return file == null ? null : _media(file, PickedMediaKind.image);
  }

  @override
  Future<SystemPickedMedia?> pickVideo({bool capture = false}) async {
    final file = await _picker.pickVideo(
      source: capture ? ImageSource.camera : ImageSource.gallery,
    );
    return file == null ? null : _media(file, PickedMediaKind.video);
  }

  @override
  Future<List<SystemPickedMedia>> recoverInterruptedPick() async {
    final response = await _picker.retrieveLostData();
    if (response.isEmpty || response.files == null) return const [];
    final kind = response.type == RetrieveType.video
        ? PickedMediaKind.video
        : PickedMediaKind.image;
    return response.files!.map((file) => _media(file, kind)).toList();
  }

  SystemPickedMedia _media(XFile file, PickedMediaKind kind) {
    return SystemPickedMedia(
      path: file.path,
      name: file.name,
      kind: kind,
      mimeType: file.mimeType,
    );
  }
}
