import '../../data/files/profile_file_store.dart';
import '../camera/system_media_picker.dart';
import '../files/system_file_picker.dart';
import '../permissions/permission_gateway.dart';

enum FileAcquisitionStatus {
  acquired,
  cancelled,
  permissionDenied,
  settingsRequired,
  restricted,
  limitExceeded,
  failed,
}

class FileAcquisitionResult {
  const FileAcquisitionResult({
    required this.status,
    this.files = const [],
    this.permission,
  });

  final FileAcquisitionStatus status;
  final List<StoredLocalFile> files;
  final PermissionDecision? permission;

  bool get acquired =>
      status == FileAcquisitionStatus.acquired && files.isNotEmpty;
}

class NativeFileAcquisitionCoordinator {
  const NativeFileAcquisitionCoordinator({
    required this.store,
    required this.permissions,
    required this.mediaPicker,
    required this.filePicker,
  });

  final ProfileFileStore store;
  final PermissionGateway permissions;
  final SystemMediaPicker mediaPicker;
  final SystemFilePicker filePicker;

  Future<FileAcquisitionResult> capturePhoto({
    required String fileId,
    required String owner,
    required String purpose,
    String sensitivity = 'private',
  }) async {
    final permission = await permissions.requestWhenNeeded(
      MakoloPermission.camera,
    );
    if (!permission.permitsCapability) {
      return _permissionResult(permission);
    }

    final picked = await mediaPicker.pickImage(capture: true);
    if (picked == null) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.cancelled,
      );
    }
    return _stageMedia(
      fileId: fileId,
      owner: owner,
      purpose: purpose,
      sensitivity: sensitivity,
      media: picked,
    );
  }

  Future<FileAcquisitionResult> pickPhoto({
    required String fileId,
    required String owner,
    required String purpose,
    String sensitivity = 'private',
  }) async {
    final picked = await mediaPicker.pickImage();
    if (picked == null) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.cancelled,
      );
    }
    return _stageMedia(
      fileId: fileId,
      owner: owner,
      purpose: purpose,
      sensitivity: sensitivity,
      media: picked,
    );
  }

  Future<FileAcquisitionResult> pickPhotos({
    required String owner,
    required String purpose,
    required String Function(int index, SystemPickedMedia media) fileIdFor,
    int maxFiles = 10,
    String sensitivity = 'private',
  }) async {
    final picker = mediaPicker;
    final List<SystemPickedMedia> picked;
    if (picker is SystemMultiImagePicker) {
      final multiPicker = picker as SystemMultiImagePicker;
      picked = await multiPicker.pickImages(limit: maxFiles);
    } else {
      final single = await picker.pickImage();
      picked = single == null ? const [] : [single];
    }
    if (picked.isEmpty) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.cancelled,
      );
    }
    if (picked.length > maxFiles) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.limitExceeded,
      );
    }
    final staged = <StoredLocalFile>[];
    try {
      for (var i = 0; i < picked.length; i++) {
        final image = picked[i];
        final result = await _stageMedia(
          fileId: fileIdFor(i, image),
          owner: owner,
          purpose: purpose,
          sensitivity: sensitivity,
          media: image,
        );
        if (!result.acquired) throw StateError('Image cannot be staged');
        staged.add(result.files.single);
      }
      return FileAcquisitionResult(
        status: FileAcquisitionStatus.acquired,
        files: staged,
      );
    } on Object {
      for (final file in staged) {
        await store.remove(file.fileId);
      }
      return const FileAcquisitionResult(status: FileAcquisitionStatus.failed);
    }
  }

  Future<FileAcquisitionResult> pickFiles({
    required String owner,
    required String purpose,
    required String Function(int index, PickedSystemFile file) fileIdFor,
    String sensitivity = 'private',
    List<String>? allowedExtensions,
    int? maxFiles,
  }) async {
    final picked = await filePicker.pick(allowedExtensions: allowedExtensions);
    if (maxFiles != null && picked.length > maxFiles) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.limitExceeded,
      );
    }
    if (picked.isEmpty) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.cancelled,
      );
    }

    final staged = <StoredLocalFile>[];
    try {
      for (var index = 0; index < picked.length; index += 1) {
        final source = picked[index];
        staged.add(
          await store.stageCopy(
            fileId: fileIdFor(index, source),
            owner: owner,
            sourceFilename: source.name,
            purpose: purpose,
            sensitivity: sensitivity,
            writeTo: source.copyTo,
          ),
        );
      }
      return FileAcquisitionResult(
        status: FileAcquisitionStatus.acquired,
        files: staged,
      );
    } on Object {
      for (final file in staged) {
        await store.remove(file.fileId);
      }
      return const FileAcquisitionResult(status: FileAcquisitionStatus.failed);
    }
  }

  Future<FileAcquisitionResult> recoverInterruptedMedia({
    required String owner,
    required String purpose,
    required String Function(int index, SystemPickedMedia media) fileIdFor,
    String sensitivity = 'private',
  }) async {
    final recovered = await mediaPicker.recoverInterruptedPick();
    if (recovered.isEmpty) {
      return const FileAcquisitionResult(
        status: FileAcquisitionStatus.cancelled,
      );
    }

    final staged = <StoredLocalFile>[];
    try {
      for (var index = 0; index < recovered.length; index += 1) {
        final media = recovered[index];
        final result = await _stageMedia(
          fileId: fileIdFor(index, media),
          owner: owner,
          purpose: purpose,
          sensitivity: sensitivity,
          media: media,
        );
        if (!result.acquired) {
          throw StateError('Recovered media was not staged.');
        }
        staged.add(result.files.single);
      }
      return FileAcquisitionResult(
        status: FileAcquisitionStatus.acquired,
        files: staged,
      );
    } on Object {
      for (final file in staged) {
        await store.remove(file.fileId);
      }
      return const FileAcquisitionResult(status: FileAcquisitionStatus.failed);
    }
  }

  Future<FileAcquisitionResult> _stageMedia({
    required String fileId,
    required String owner,
    required String purpose,
    required String sensitivity,
    required SystemPickedMedia media,
  }) async {
    try {
      final staged = await store.stage(
        fileId: fileId,
        owner: owner,
        sourcePath: media.path,
        purpose: purpose,
        sensitivity: sensitivity,
      );
      return FileAcquisitionResult(
        status: FileAcquisitionStatus.acquired,
        files: [staged],
      );
    } on Object {
      return const FileAcquisitionResult(status: FileAcquisitionStatus.failed);
    }
  }

  FileAcquisitionResult _permissionResult(PermissionDecision permission) {
    final status = switch (permission) {
      PermissionDecision.permanentlyDenied =>
        FileAcquisitionStatus.settingsRequired,
      PermissionDecision.restricted => FileAcquisitionStatus.restricted,
      _ => FileAcquisitionStatus.permissionDenied,
    };
    return FileAcquisitionResult(status: status, permission: permission);
  }
}
