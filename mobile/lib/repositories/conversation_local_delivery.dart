import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:drift/drift.dart';

import '../platform/files/native_directories.dart';

import '../auth/token_store.dart';
import '../data/local/makolo_database.dart';
import '../data/files/profile_paths.dart';
import '../data/files/profile_file_store.dart';
import '../data/files/file_transfer_coordinator.dart';
import '../network/makolo_api_client.dart';
import '../repositories/draft_repository.dart';
import '../sync/outbox/outbox_processor.dart';
import '../sync/outbox/outbox_repository.dart';

class ConversationTransfer {
  const ConversationTransfer(
    this.state, {
    this.transferred = 0,
    this.total = 0,
  });
  final FileTransferState state;
  final int transferred;
  final int total;
}

class _ConversationMediaOwner implements FileOwnerTransfer {
  _ConversationMediaOwner(this.send, this.cancelHandle);
  final Future<ApiResponse> Function(
    StoredLocalFile file,
    FileTransferProgress? progress,
  )
  send;
  final MakoloCancelHandle cancelHandle;
  ApiResponse? response;
  @override
  Future<FileTransferReceipt> upload({
    required StoredLocalFile file,
    FileTransferProgress? onProgress,
  }) async {
    response = await send(file, onProgress);
    final ack = response!.jsonObject();
    return FileTransferReceipt(
      confirmed:
          ack['point_id'] is String &&
          (ack['attachment'] is Map ||
              (ack['status'] == 'confirmed' &&
                  ack['removed'] == true &&
                  ack['entry_id'] is String)),
    );
  }

  @override
  Future<void> cancel(String fileId) async {
    cancelHandle.cancel();
  }
}

/// One local intent belongs to one authenticated Profile and Conversation.
/// This is transport metadata, not a second authority for canonical Points.
class ConversationOutgoing {
  const ConversationOutgoing({
    required this.reference,
    required this.kind,
    required this.title,
    required this.body,
    required this.observedAt,
    required this.state,
    this.retryScheduled = false,
    this.remotePointId,
    this.pointId,
    this.representedSpaceId,
    this.responseValue,
    this.mediaKind,
    this.filename,
    this.localFilePath,
    this.semanticMedia = const [],
    this.options = const [],
  });

  final String reference;
  final String kind;
  final String title;
  final String body;
  final DateTime observedAt;
  final String state;

  /// The owner outbox will retry this exact idempotent intent in foreground.
  final bool retryScheduled;
  final String? remotePointId;
  final String? pointId;
  final String? representedSpaceId;
  final Object? responseValue;
  final String? mediaKind;
  final String? filename;
  final String? localFilePath;
  final List<Map<String, dynamic>> semanticMedia;
  final List<String> options;

  bool get isConfirmed => state == OutboxState.confirmed.wireValue;
  bool get isBlocked =>
      state == OutboxState.conflict.wireValue ||
      state == OutboxState.awaitingConfirmation.wireValue ||
      (state == OutboxState.failed.wireValue);
}

/// Conversation C3_bus reuses the existing DraftRepository/OutboxProcessor.
/// Enqueue is durable before any network request and replay uses precisely
/// the same client_reference; the owner is always authoritative.
class ConversationLocalDelivery {
  ConversationLocalDelivery({
    required this.database,
    required this.drafts,
    required this.outbox,
    required this.tokens,
    required this.api,
    required this.profileId,
    required this.refreshDetail,
    required this.mediaMime,
    this.mediaDirectory,
  }) {
    if (profileId != drafts.profileId ||
        profileId != outbox.profileId ||
        !identical(database, drafts.database) ||
        !identical(database, outbox.database)) {
      throw ArgumentError('Conversation delivery requires one Profile scope');
    }
  }

  static const owner = 'Conversations';
  static const operationKind = 'conversation.point.compose';
  static const composeDraftKind = 'conversation.compose.draft';
  static const outgoingDraftKind = 'conversation.compose.outgoing';

  final MakoloDatabase database;
  final DraftRepository drafts;
  final OutboxRepository outbox;
  final TokenStore tokens;
  final MakoloApiClient api;
  final String profileId;
  final Future<void> Function(String conversationId, String? focusPointId)
  refreshDetail;
  final String Function(String filename, String kind) mediaMime;
  final Future<Directory> Function()? mediaDirectory;

  Future<void> Function()? requestDispatch;

  Future<ProfileFileStore>? _files;
  final _transferUpdates =
      StreamController<MapEntry<String, ConversationTransfer>>.broadcast();
  final Map<String, ConversationTransfer> _transfers = {};
  final Map<String, MakoloCancelHandle> _transferCancels = {};
  Future<ProfileFileStore> _fileStore() => _files ??= () async {
    if (mediaDirectory == null)
      return ProfileFileStore.open(database: database, profileId: profileId);
    final root = await mediaDirectory!();
    return ProfileFileStore(
      database: database,
      profileId: profileId,
      privateDirectory: Directory('${root.path}/private'),
      stagingDirectory: Directory('${root.path}/staging'),
    );
  }();
  Stream<ConversationTransfer?> watchTransfer(String reference) async* {
    yield _transfers[reference];
    yield* _transferUpdates.stream
        .where((entry) => entry.key == reference)
        .map((entry) => entry.value);
  }

  void _transfer(String reference, ConversationTransfer progress) {
    _transfers[reference] = progress;
    _transferUpdates.add(MapEntry(reference, progress));
  }

  void cancelTransfer(String reference) =>
      _transferCancels[reference]?.cancel();

  Future<ApiResponse> _uploadIntent(
    String reference,
    String path, {
    required Map<String, Object?> fields,
    required List<MakoloUploadFile> files,
    String? fileId,
  }) async {
    final cancel = MakoloCancelHandle();
    _transferCancels[reference] = cancel;
    void progress(int sent, int total) => _transfer(
      reference,
      ConversationTransfer(
        FileTransferState.transferring,
        transferred: sent,
        total: total,
      ),
    );
    _transfer(
      reference,
      const ConversationTransfer(FileTransferState.transferring),
    );
    try {
      if (fileId == null)
        return await api.upload(
          path,
          fields: fields,
          files: files,
          headers: {'X-Makolo-Profile': profileId},
          cancel: cancel,
          onProgress: progress,
        );
      final store = await _fileStore();
      final owner = _ConversationMediaOwner(
        (file, onProgress) => api.upload(
          path,
          fields: fields,
          files: [
            MakoloUploadFile(
              fieldName: 'file',
              path: file.path,
              filename: files.single.filename,
            ),
          ],
          headers: {'X-Makolo-Profile': profileId},
          cancel: cancel,
          onProgress: onProgress,
        ),
        cancel,
      );
      final result = await FileTransferCoordinator(store).transferToOwner(
        fileId: fileId,
        owner: owner,
        onProgress: progress,
        onState: (state) => _transfer(reference, ConversationTransfer(state)),
      );
      if (result.receipt?.confirmed != true && owner.response == null)
        throw StateError('Owner confirmation unavailable');
      return owner.response!;
    } on Object {
      _transfer(
        reference,
        ConversationTransfer(
          cancel.isCancelled
              ? FileTransferState.ownerConfirmationRequired
              : FileTransferState.failedRecoverable,
        ),
      );
      rethrow;
    } finally {
      _transferCancels.remove(reference);
    }
  }

  static String _reference() {
    final random = Random.secure();
    return 'conv-${DateTime.now().toUtc().microsecondsSinceEpoch}-'
        '${random.nextInt(0x7fffffff).toRadixString(16)}';
  }

  static String _draftScope(String conversationId, String kind) =>
      '$conversationId:$kind';

  Future<Map<String, dynamic>?> readDraft({
    required String conversationId,
    required String kind,
  }) async {
    final record = await drafts.read(
      owner: owner,
      resourceKind: composeDraftKind,
      resourceId: _draftScope(conversationId, kind),
    );
    return record?.payload;
  }

  Future<void> saveDraft({
    required String conversationId,
    required String kind,
    required Map<String, dynamic> payload,
  }) => drafts.saveLocal(
    draftId: 'conv:draft:$profileId:${_draftScope(conversationId, kind)}',
    owner: owner,
    resourceKind: composeDraftKind,
    resourceId: _draftScope(conversationId, kind),
    payload: payload,
  );

  Future<void> clearDraft({
    required String conversationId,
    required String kind,
  }) => drafts
      .delete(
        owner: owner,
        resourceKind: composeDraftKind,
        resourceId: _draftScope(conversationId, kind),
      )
      .then((_) {});

  Future<List<Map<String, dynamic>>> _stageSemanticMedia(
    String reference,
    List<Map<String, dynamic>> media,
  ) async {
    if (media.isEmpty || media.length > 24) {
      throw ArgumentError('Entre 1 et 24 médias sont nécessaires.');
    }
    final folder = mediaDirectory == null
        ? Directory(
            '${(await NativeDirectories.support()).path}/profiles/'
            '${ProfilePaths.safeProfileId(profileId)}/conversation-outgoing',
          )
        : await mediaDirectory!();
    await folder.create(recursive: true);
    final staged = <Map<String, dynamic>>[];
    try {
      for (var index = 0; index < media.length; index++) {
        final entry = media[index];
        final path = entry['path']?.toString() ?? '';
        final filename = entry['filename']?.toString() ?? '';
        final kind = entry['kind']?.toString() ?? '';
        if (path.isEmpty ||
            filename.isEmpty ||
            !{'image', 'file', 'voice', 'audio', 'video'}.contains(kind)) {
          throw ArgumentError('Média structuré invalide.');
        }
        final source = File(path);
        if (!await source.exists()) {
          throw StateError('Un fichier sélectionné est introuvable.');
        }
        final name = filename.split(RegExp(r'[/\\]')).last;
        final dot = name.lastIndexOf('.');
        final suffix = dot > 0 ? name.substring(dot) : '.bin';
        final ext = RegExp(r'^\.[A-Za-z0-9]{1,10}$').hasMatch(suffix)
            ? suffix
            : '.bin';
        final copy = '${folder.path}/$reference-$index$ext';
        await source.copy(copy);
        staged.add({...entry, 'path': copy, 'filename': name});
      }
    } on Object {
      for (final item in staged) {
        try {
          await File(item['path'].toString()).delete();
        } on Object {
          // Do not conceal the initial staging failure.
        }
      }
      rethrow;
    }
    return staged;
  }

  /// Full immutable owner request, with a stable idempotence reference.
  /// The conversation may be offline: queueing never requires API access.
  Future<String> queue({
    required String conversationId,
    required String mode,
    String? kind,
    String? body,
    String? title,
    List<String>? options,
    bool multipleChoice = false,
    String? formVersionId,
    List<String>? questions,
    String? pointId,
    Object? responseValue,
    String? replyToId,
    List<String>? mentionProfileIds,
    List<Map<String, dynamic>>? references,
    String? audienceId,
    String? representedSpaceId,
    String? filePath,
    String? filename,
    String? mediaKind,
    String? pointKind,
    List<Map<String, dynamic>>? semanticMedia,
  }) async {
    if (conversationId.trim().isEmpty ||
        !{
          'text',
          'point',
          'form',
          'media',
          'semantic_media',
          'response',
          'media_response',
        }.contains(mode)) {
      throw ArgumentError('Unsupported conversation composition');
    }
    if (mode == 'response' &&
        ((pointId ?? '').isEmpty || responseValue == null)) {
      throw ArgumentError('A Point and a response value are required');
    }
    if (mode == 'media_response' && (pointId ?? '').isEmpty) {
      throw ArgumentError('A Point is required for a media response');
    }
    final reference = _reference();
    final deviceId = await tokens.deviceInstanceId();
    String? stagedPath;
    final stagedSemantic = mode == 'semantic_media'
        ? await _stageSemanticMedia(reference, semanticMedia ?? const [])
        : <Map<String, dynamic>>[];
    if (mode == 'media' || mode == 'media_response') {
      if (filePath == null ||
          filename == null ||
          mediaKind == null ||
          !{'image', 'file', 'voice', 'audio', 'video'}.contains(mediaKind)) {
        throw ArgumentError('A selected media file is required');
      }
      final original = File(filePath);
      if (!await original.exists()) {
        throw StateError('Le fichier sélectionné est introuvable.');
      }
      final store = await _fileStore();
      final staged = await store.stage(
        fileId: reference,
        owner: owner,
        sourcePath: original.path,
        purpose: 'conversation.outgoing',
        sensitivity: 'private',
      );
      stagedPath = staged.path;
    }
    final request = <String, dynamic>{
      'conversation_id': conversationId,
      'mode': mode,
      'client_reference': reference,
      'kind': ?kind,
      'body': ?body,
      'title': ?title,
      'options': ?options,
      if (multipleChoice) 'multiple_choice': true,
      'form_version_id': ?formVersionId,
      'questions': ?questions,
      'point_id': ?pointId,
      'value': ?responseValue,
      'reply_to_id': ?replyToId,
      'mention_profile_ids': ?mentionProfileIds,
      'references': ?references,
      'audience_id': ?audienceId,
      'represented_space_id': ?representedSpaceId,
      'local_file_path': ?stagedPath,
      if (stagedPath != null) 'local_file_id': reference,
      'filename': ?filename,
      'media_kind': ?mediaKind,
      'point_kind': ?pointKind,
      if (stagedSemantic.isNotEmpty) 'semantic_media': stagedSemantic,
    };
    // Draft identity is per intent, while the Outbox resource is the
    // Conversation: several outgoing Points can coexist safely.
    try {
      await drafts.saveAndQueue(
        draftId: 'conv:out:$profileId:$reference',
        owner: owner,
        resourceKind: outgoingDraftKind,
        resourceId: reference,
        operationResourceId: conversationId,
        payload: request,
        operationPayload: request,
        operationId: '$deviceId:$reference',
        deviceInstanceId: deviceId,
        operationKind: operationKind,
        intentId: reference,
        replayPolicy: ReplayPolicy.idempotent,
        ownerIdempotencyKey: reference,
      );
    } on Object {
      if (stagedPath != null) {
        try {
          if (mode == 'media' || mode == 'media_response') {
            await (await _fileStore()).remove(reference);
          } else {
            await File(stagedPath).delete();
          }
        } on Object {
          // Best-effort cleanup: preserve the original dispatch failure.
        }
      }
      for (final item in stagedSemantic) {
        try {
          await File(item['path'].toString()).delete();
        } on Object {
          // Keep the initial draft-queue failure.
        }
      }
      rethrow;
    }
    final dispatch = requestDispatch;
    if (dispatch != null) {
      unawaited(
        () async {
          // Another drain may already be running when this intent is queued.
          // The second pass picks up rows added after its pending snapshot.
          await dispatch();
          await dispatch();
        }().catchError((Object _) {}),
      );
    }
    return reference;
  }

  /// Immutable pending attempts are projected into the Conversation without
  /// claiming they are already accepted or read by remote participants.
  Stream<List<ConversationOutgoing>> watchOutgoing(String conversationId) {
    final query = database.select(database.outboxOperations)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.owner.equals(owner) &
            row.operationKind.equals(operationKind) &
            row.resourceId.equals(conversationId),
      )
      ..orderBy([(row) => OrderingTerm.asc(row.observedAt)]);
    return query.watch().map(
      (rows) => [
        for (final row in rows)
          if (row.state != OutboxState.cancelled.wireValue) _row(row),
      ],
    );
  }

  ConversationOutgoing _row(OutboxOperation row) {
    final payload = jsonDecode(row.payloadJson) as Map<String, dynamic>;
    final mode = payload['mode']?.toString();
    return ConversationOutgoing(
      reference: row.intentId,
      pointId: payload['point_id']?.toString(),
      representedSpaceId: payload['represented_space_id']?.toString(),
      responseValue: payload['value'],
      kind: mode == 'response' || mode == 'media_response'
          ? 'response'
          : mode == 'form'
          ? 'form_request'
          : mode == 'media'
          ? payload['point_kind']?.toString() ?? 'information'
          : mode == 'text'
          ? 'information'
          : payload['kind']?.toString() ?? 'information',
      title: payload['title']?.toString() ?? '',
      body: payload['body']?.toString() ?? '',
      observedAt: row.observedAt,
      state: row.state,
      retryScheduled:
          row.state == OutboxState.failed.wireValue &&
          OutboxRepository.retryableErrorCodes.contains(row.lastErrorCode),
      mediaKind: payload['media_kind']?.toString(),
      filename: payload['filename']?.toString(),
      localFilePath: payload['local_file_path']?.toString(),
      semanticMedia: [
        for (final item
            in payload['semantic_media'] is List
                ? payload['semantic_media'] as List
                : const [])
          if (item is Map)
            item.map((key, value) => MapEntry(key.toString(), value)),
      ],
      options: [
        for (final item
            in payload['options'] is List
                ? payload['options'] as List
                : const [])
          item.toString(),
      ],
    );
  }

  Future<OutboxResolution> handle(OutboxOperation operation) async {
    if (operation.profileId != profileId ||
        operation.owner != owner ||
        operation.operationKind != operationKind) {
      return OutboxResolution.conflict;
    }
    final session = await tokens.readSession();
    if (session?.profileId != profileId) {
      return OutboxResolution.awaitingConfirmation;
    }
    final payload = jsonDecode(operation.payloadJson);
    if (payload is! Map<String, dynamic> ||
        payload['client_reference'] != operation.ownerIdempotencyKey ||
        payload['client_reference'] != operation.intentId) {
      return OutboxResolution.conflict;
    }
    final conversationId = payload['conversation_id']?.toString() ?? '';
    final mode = payload['mode']?.toString() ?? '';
    if (conversationId.isEmpty ||
        operation.resourceId != conversationId ||
        !{
          'text',
          'point',
          'form',
          'media',
          'semantic_media',
          'response',
          'media_response',
        }.contains(mode)) {
      return OutboxResolution.conflict;
    }
    final Map<String, dynamic> confirmed;
    if (mode == 'response') {
      final pointId = payload['point_id']?.toString() ?? '';
      if (pointId.isEmpty ||
          !payload.containsKey('value') ||
          payload['value'] == null) {
        return OutboxResolution.conflict;
      }
      final response = await api.post(
        'api/v1/conversations/points/$pointId/respond/',
        body: {
          'value': payload['value'],
          'client_reference': operation.intentId,
          'represented_space_id': payload['represented_space_id'],
        },
        headers: {'X-Makolo-Profile': profileId},
      );
      confirmed = response.jsonObject();
      if (confirmed['point_id']?.toString() != pointId ||
          confirmed['id'] == null ||
          !{'active', 'superseded'}.contains(confirmed['status'])) {
        return OutboxResolution.awaitingConfirmation;
      }
    } else if (mode == 'media_response') {
      final pointId = payload['point_id']?.toString() ?? '';
      final path = payload['local_file_path']?.toString() ?? '';
      final filename = payload['filename']?.toString() ?? '';
      final kind = payload['media_kind']?.toString() ?? '';
      if (pointId.isEmpty ||
          path.isEmpty ||
          filename.isEmpty ||
          !{'file', 'image', 'voice', 'audio'}.contains(kind) ||
          !await File(path).exists()) {
        return OutboxResolution.conflict;
      }
      final response = await _uploadIntent(
        operation.intentId,
        'api/v1/conversations/points/$pointId/reply-media/',
        fileId: payload['local_file_id']?.toString(),
        fields: {
          'client_reference': operation.intentId,
          'kind': kind,
          'mime_type': mediaMime(filename, kind),
          'represented_space_id': payload['represented_space_id'],
        },
        files: [
          MakoloUploadFile(fieldName: 'file', path: path, filename: filename),
        ],
      );
      confirmed = response.jsonObject();
      if (confirmed['point_id']?.toString() != pointId ||
          confirmed['response_id'] is! String ||
          confirmed['attachment'] is! Map) {
        return OutboxResolution.awaitingConfirmation;
      }
    } else if (mode == 'semantic_media') {
      final raw = payload['semantic_media'];
      if (raw is! List || raw.isEmpty || raw.length > 24) {
        return OutboxResolution.conflict;
      }
      final files = <MakoloUploadFile>[];
      final manifest = <Map<String, dynamic>>[];
      for (var index = 0; index < raw.length; index++) {
        final item = raw[index];
        if (item is! Map) return OutboxResolution.conflict;
        final path = item['path']?.toString() ?? '';
        final filename = item['filename']?.toString() ?? '';
        final kind = item['kind']?.toString() ?? '';
        if (path.isEmpty ||
            filename.isEmpty ||
            !{'image', 'file', 'voice', 'audio', 'video'}.contains(kind) ||
            !await File(path).exists()) {
          return OutboxResolution.conflict;
        }
        final field = 'media_$index';
        manifest.add({
          'field': field,
          'scope': item['scope'],
          if (item['scope'] == 'option') 'option_index': item['option_index'],
          'kind': kind,
          'caption': item['caption']?.toString() ?? '',
          'mime_type': mediaMime(filename, kind),
        });
        files.add(
          MakoloUploadFile(fieldName: field, path: path, filename: filename),
        );
      }
      final response = await _uploadIntent(
        operation.intentId,
        'api/v1/conversations/$conversationId/semantic-media/',
        fields: {
          'client_reference': operation.intentId,
          'kind': payload['kind'],
          'title': payload['title'],
          'body': payload['body'],
          'options': jsonEncode(payload['options'] ?? <String>[]),
          'multiple_choice': payload['multiple_choice'] == true
              ? 'true'
              : 'false',
          'media_manifest': jsonEncode(manifest),
          'audience_id': payload['audience_id'],
          'represented_space_id': payload['represented_space_id'],
        },
        files: files,
      );
      confirmed = response.jsonObject();
      if (confirmed['attachments'] is! List) {
        return OutboxResolution.awaitingConfirmation;
      }
    } else if (mode == 'media') {
      final localFile = payload['local_file_path']?.toString() ?? '';
      final filename = payload['filename']?.toString() ?? '';
      final kind = payload['media_kind']?.toString() ?? '';
      if (localFile.isEmpty ||
          filename.isEmpty ||
          kind.isEmpty ||
          !await File(localFile).exists()) {
        return OutboxResolution.conflict;
      }
      final response = await _uploadIntent(
        operation.intentId,
        'api/v1/conversations/$conversationId/media/',
        fileId: payload['local_file_id']?.toString(),
        fields: {
          'client_reference': operation.intentId,
          'kind': kind,
          'mime_type': mediaMime(filename, kind),
          'body': payload['body'] ?? '',
          'point_id': payload['point_id'],
          'audience_id': payload['audience_id'],
          'represented_space_id': payload['represented_space_id'],
          'point_kind': payload['point_kind'],
          'title': payload['title'],
          'options': payload['options'] == null
              ? null
              : jsonEncode(payload['options']),
          'multiple_choice': payload['multiple_choice'] == true,
          'form_version_id': payload['form_version_id'],
          'questions': payload['questions'] == null
              ? null
              : jsonEncode(payload['questions']),
        },
        files: [
          MakoloUploadFile(
            fieldName: 'file',
            path: localFile,
            filename: filename,
          ),
        ],
      );
      confirmed = response.jsonObject();
      if (confirmed['attachment'] is! Map &&
          !(confirmed['removed'] == true &&
              confirmed['status'] == 'confirmed' &&
              confirmed['entry_id'] is String)) {
        return OutboxResolution.awaitingConfirmation;
      }
    } else {
      final endpoint = mode == 'form'
          ? 'api/v1/conversations/$conversationId/forms/'
          : 'api/v1/conversations/$conversationId/compose/';
      final data = Map<String, dynamic>.from(payload)
        ..remove('conversation_id');
      final response = await api.post(
        endpoint,
        body: data,
        headers: {'X-Makolo-Profile': profileId},
      );
      confirmed = response.jsonObject();
    }
    if (mode == 'text' &&
        payload['point_id'] != null &&
        (confirmed['status'] != 'confirmed' ||
            confirmed['entry_id'] is! String ||
            confirmed['sequence'] is! int)) {
      return OutboxResolution.awaitingConfirmation;
    }
    final remoteId = confirmed['point_id']?.toString();
    if (remoteId == null || remoteId.isEmpty) {
      // The owner may have accepted it, but its identity is not verified.
      return OutboxResolution.awaitingConfirmation;
    }
    try {
      await refreshDetail(conversationId, remoteId);
    } on Object {
      // Confirmed owner result is not undone by a failed projection pull.
    }
    // Outbox keeps its confirmed state for safe local reconciliation.
    return OutboxResolution.confirmed;
  }
}
