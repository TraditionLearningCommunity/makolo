import 'dart:io';

import '../../data/files/profile_file_store.dart';
import '../../network/makolo_api_client.dart';

/// Optional, explicit recorded-file transcription through an authenticated
/// owner. No local speech result is inferred, and an unavailable service is
/// never shown as a usable Mark action.
class MarkRecordedAudioTranscriber {
  const MarkRecordedAudioTranscriber(this.api);

  final MakoloApiClient api;

  static const path = 'api/v1/me/mark/transcription/';
  static const maxBytes = 25 * 1024 * 1024;

  Future<bool> available() async {
    try {
      final response = await api.get(path);
      final payload = response.jsonObject()['data'];
      return payload is Map && payload['available'] == true;
    } on Object {
      return false;
    }
  }

  Future<String> transcribe(
    StoredLocalFile file, {
    required String activeProfileId,
  }) async {
    if (file.profileId != activeProfileId ||
        file.owner != 'profile' ||
        file.purpose != 'mark_intake' ||
        file.sensitivity != 'private') {
      throw StateError('Recording does not belong to the active Profile.');
    }
    final source = File(file.path);
    final size = await source.length();
    if (size == 0 || size > maxBytes) {
      throw const FileSystemException('Recording size is unsupported.');
    }
    // The audio is uploaded only after the person's explicit Transcrire tap.
    final response = await api.upload(
      path,
      files: [
        MakoloUploadFile(
          fieldName: 'audio',
          path: file.path,
          filename: 'enregistrement.m4a',
          contentType: 'audio/mp4',
        ),
      ],
    );
    final payload = response.jsonObject()['data'];
    if (payload is! Map || payload['text'] is! String) {
      throw const FormatException('No recorded-audio transcript provided.');
    }
    final text = (payload['text'] as String).trim();
    if (text.isEmpty) throw const FormatException('Empty transcript.');
    return text;
  }
}
