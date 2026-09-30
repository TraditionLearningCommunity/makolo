import '../../data/files/profile_file_store.dart';
import 'system_share_receiver.dart';

class InboundSharedCapture {
  const InboundSharedCapture({
    required this.kind,
    this.text,
    this.url,
    this.files = const [],
  });

  final SharedPayloadKind kind;
  final String? text;
  final Uri? url;
  final List<StoredLocalFile> files;
}

class SharedPayloadCoordinator {
  const SharedPayloadCoordinator(this.store);

  final ProfileFileStore store;

  Future<InboundSharedCapture> capture(
    SharedPayload payload, {
    required String Function(int index, SharedFileReference file) fileIdFor,
    String owner = 'InboundCapture',
    String purpose = 'share-ingress',
    String sensitivity = 'private',
  }) async {
    if (payload.kind == SharedPayloadKind.text) {
      return InboundSharedCapture(kind: payload.kind, text: payload.text);
    }
    if (payload.kind == SharedPayloadKind.url) {
      return InboundSharedCapture(kind: payload.kind, url: payload.url);
    }

    final staged = <StoredLocalFile>[];
    try {
      for (var index = 0; index < payload.files.length; index += 1) {
        final source = payload.files[index];
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
      return InboundSharedCapture(kind: payload.kind, files: staged);
    } on Object {
      for (final file in staged) {
        await store.remove(file.fileId);
      }
      rethrow;
    }
  }
}
