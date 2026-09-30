import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/platform/camera/system_media_picker.dart';
import 'package:makolo_mobile/platform/files/native_file_acquisition.dart';
import 'package:makolo_mobile/platform/files/system_file_picker.dart';
import 'package:makolo_mobile/platform/permissions/permission_gateway.dart';

class FakePermissions implements PermissionGateway {
  FakePermissions(this.decision);

  PermissionDecision decision;

  @override
  Future<bool> openSettings() async => true;

  @override
  Future<PermissionDecision> request(MakoloPermission permission) async =>
      decision;

  @override
  Future<PermissionDecision> status(MakoloPermission permission) async =>
      decision;
}

class FakeMediaPicker implements SystemMediaPicker {
  FakeMediaPicker({this.image});

  final SystemPickedMedia? image;
  int imageCalls = 0;

  @override
  Future<SystemPickedMedia?> pickImage({bool capture = false}) async {
    imageCalls += 1;
    return image;
  }

  @override
  Future<SystemPickedMedia?> pickVideo({bool capture = false}) async => null;

  @override
  Future<List<SystemPickedMedia>> recoverInterruptedPick() async => const [];
}

class FakeFilePicker implements SystemFilePicker {
  FakeFilePicker(this.files);

  final List<PickedSystemFile> files;

  @override
  Future<List<PickedSystemFile>> pick({
    List<String>? allowedExtensions,
  }) async => files;
}

void main() {
  test('camera denial does not invoke the media picker', () async {
    final root = await Directory.systemTemp.createTemp('makolo-nc-denied-');
    final database = MakoloDatabase.memory();
    addTearDown(() async {
      await database.close();
      await root.delete(recursive: true);
    });
    final picker = FakeMediaPicker();
    final coordinator = NativeFileAcquisitionCoordinator(
      store: ProfileFileStore(
        database: database,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/private'),
        stagingDirectory: Directory('${root.path}/staging'),
      ),
      permissions: FakePermissions(PermissionDecision.permanentlyDenied),
      mediaPicker: picker,
      filePicker: FakeFilePicker(const []),
    );

    final result = await coordinator.capturePhoto(
      fileId: 'capture-1',
      owner: 'InboundCapture',
      purpose: 'camera',
    );

    expect(result.status, FileAcquisitionStatus.settingsRequired);
    expect(picker.imageCalls, 0);
  });

  test('system file picker stages bytes into the Profile sandbox', () async {
    final root = await Directory.systemTemp.createTemp('makolo-nc-picker-');
    final database = MakoloDatabase.memory();
    addTearDown(() async {
      await database.close();
      await root.delete(recursive: true);
    });
    final staging = Directory('${root.path}/profile-a/staging');
    final coordinator = NativeFileAcquisitionCoordinator(
      store: ProfileFileStore(
        database: database,
        profileId: 'profile-a',
        privateDirectory: Directory('${root.path}/profile-a/private'),
        stagingDirectory: staging,
      ),
      permissions: FakePermissions(PermissionDecision.granted),
      mediaPicker: FakeMediaPicker(),
      filePicker: FakeFilePicker([
        PickedSystemFile(
          name: 'private-note.pdf',
          byteLength: 4,
          copyTo: (destinationPath) =>
              File(destinationPath).writeAsBytes([1, 2, 3, 4]),
        ),
      ]),
    );

    final result = await coordinator.pickFiles(
      owner: 'InboundCapture',
      purpose: 'share',
      fileIdFor: (_, __) => 'opaque-file-1',
    );

    expect(result.acquired, isTrue);
    expect(result.files.single.profileId, 'profile-a');
    expect(result.files.single.owner, 'InboundCapture');
    expect(result.files.single.path, startsWith(staging.path));
    expect(result.files.single.path, isNot(contains('private-note')));
    expect(await File(result.files.single.path).readAsBytes(), [1, 2, 3, 4]);
  });
}
