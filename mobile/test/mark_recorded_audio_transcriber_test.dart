import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/files/profile_file_store.dart';
import 'package:makolo_mobile/features/mark/mark_recorded_audio_transcriber.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

class _FakeMarkApi extends MakoloApiClient {
  _FakeMarkApi() : super(
    baseUri: Uri.parse('https://makolo.invalid/'),
    tokenStore: MemoryTokenStore(),
  );

  bool enabled = false;
  String transcript = 'Préparer une salle.';
  int uploads = 0;

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    expect(path, MarkRecordedAudioTranscriber.path);
    return ApiResponse(200, '{"data":{"available":$enabled}}', const {});
  }

  @override
  Future<ApiResponse> upload(
    String path, {
    String method = 'POST',
    Map<String, Object?> fields = const {},
    List<MakoloUploadFile> files = const [],
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) async {
    expect(path, MarkRecordedAudioTranscriber.path);
    expect(files.single.fieldName, 'audio');
    expect(files.single.contentType, 'audio/mp4');
    uploads++;
    return ApiResponse(200, '{"data":{"text":"$transcript"}}', const {});
  }
}

void main() {
  late Directory root;
  late File recording;
  late _FakeMarkApi api;
  late MarkRecordedAudioTranscriber gateway;

  setUp(() async {
    root = await Directory.systemTemp.createTemp('mark-transcription-');
    recording = File('${root.path}/test.m4a');
    await recording.writeAsBytes([1, 2, 3]);
    api = _FakeMarkApi();
    gateway = MarkRecordedAudioTranscriber(api);
  });

  tearDown(() async {
    api.close(force: true);
    await root.delete(recursive: true);
  });

  StoredLocalFile fileFor(String profileId, {String owner = 'profile'}) =>
      StoredLocalFile(
        fileId: 'audio-1',
        profileId: profileId,
        owner: owner,
        path: recording.path,
        purpose: 'mark_intake',
        sensitivity: 'private',
        reconstructible: false,
        createdAt: DateTime.now(),
      );

  test('unconfigured server capability never advertises transcription', () async {
    expect(await gateway.available(), isFalse);
    api.enabled = true;
    expect(await gateway.available(), isTrue);
  });

  test('recorded file is uploaded only after explicit transcription call', () async {
    api.enabled = true;
    final file = fileFor('profile-a');
    expect(api.uploads, 0);
    final result = await gateway.transcribe(file, activeProfileId: 'profile-a');
    expect(result, 'Préparer une salle.');
    expect(api.uploads, 1);
  });

  test('cannot transcribe another Profile or Space file', () async {
    await expectLater(
      gateway.transcribe(
        fileFor('profile-other'),
        activeProfileId: 'profile-a',
      ),
      throwsStateError,
    );
    await expectLater(
      gateway.transcribe(
        fileFor('profile-a', owner: 'space:other'),
        activeProfileId: 'profile-a',
      ),
      throwsStateError,
    );
    expect(api.uploads, 0);
  });
}
