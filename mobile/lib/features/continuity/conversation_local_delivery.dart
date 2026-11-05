import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:drift/drift.dart';
import 'package:path_provider/path_provider.dart';

import '../../auth/token_store.dart';
import '../../data/local/makolo_database.dart';
import '../../data/files/profile_paths.dart';
import '../../network/makolo_api_client.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/outbox/outbox_processor.dart';
import '../../sync/outbox/outbox_repository.dart';

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
    this.remotePointId,
    this.mediaKind,
    this.filename,
    this.localFilePath,
  });

  final String reference;
  final String kind;
  final String title;
  final String body;
  final DateTime observedAt;
  final String state;
  final String? remotePointId;
  final String? mediaKind;
  final String? filename;
  final String? localFilePath;

  bool get isConfirmed => state == OutboxState.confirmed.wireValue;
  bool get isBlocked => state == OutboxState.conflict.wireValue ||
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
    if (profileId != drafts.profileId || profileId != outbox.profileId ||
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
  }) => drafts.delete(
    owner: owner,
    resourceKind: composeDraftKind,
    resourceId: _draftScope(conversationId, kind),
  ).then((_) {});

  /// Full immutable owner request, with a stable idempotence reference.
  /// The conversation may be offline: queueing never requires API access.
  Future<String> queue({
    required String conversationId,
    required String mode,
    String? kind,
    String? body,
    String? title,
    List<String>? options,
    String? formVersionId,
    List<String>? questions,
    String? pointId,
    String? audienceId,
    String? representedSpaceId,
    String? filePath,
    String? filename,
    String? mediaKind,
    String? pointKind,
  }) async {
    if (conversationId.trim().isEmpty ||
        !{'text', 'point', 'form', 'media'}.contains(mode)) {
      throw ArgumentError('Unsupported conversation composition');
    }
    final reference = _reference();
    String? stagedPath;
    if (mode == 'media') {
      if (filePath == null || filename == null || mediaKind == null ||
          !{'image', 'file', 'voice', 'audio', 'video'}.contains(mediaKind)) {
        throw ArgumentError('A selected media file is required');
      }
      final original = File(filePath);
      if (!await original.exists()) {
        throw StateError('Le fichier sélectionné est introuvable.');
      }
      final folder = mediaDirectory == null
          ? Directory('${(await getApplicationSupportDirectory()).path}/profiles/'
              '${ProfilePaths.safeProfileId(profileId)}/conversation-outgoing')
          : await mediaDirectory!();
      await folder.create(recursive: true);
      final name = filename.split(RegExp(r'[/\\]')).last;
      final suffix = name.contains('.')
          ? name.substring(name.lastIndexOf('.')) : '.bin';
      final extension = RegExp(r'^\.[A-Za-z0-9]{1,10}.hasMatch(suffix)
              && suffix.length <= 11
          ? suffix : '.bin';
      stagedPath = '${folder.path}/$reference$extension';
      await original.copy(stagedPath);
    }
    final deviceId = await tokens.deviceInstanceId();
    final request = <String, dynamic>{
      'conversation_id': conversationId,
      'mode': mode,
      'client_reference': reference,
      if (kind != null) 'kind': kind,
      if (body != null) 'body': body,
      if (title != null) 'title': title,
      if (options != null) 'options': options,
      if (formVersionId != null) 'form_version_id': formVersionId,
      if (questions != null) 'questions': questions,
      if (pointId != null) 'point_id': pointId,
      if (audienceId != null) 'audience_id': audienceId,
      if (representedSpaceId != null) 'represented_space_id': representedSpaceId,
      if (stagedPath != null) 'local_file_path': stagedPath,
      if (filename != null) 'filename': filename,
      if (mediaKind != null) 'media_kind': mediaKind,
      if (pointKind != null) 'point_kind': pointKind,
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
        try { await File(stagedPath).delete(); } on Object {}
      }
      rethrow;
    }
    final dispatch = requestDispatch;
    if (dispatch != null) unawaited(dispatch().catchError((Object _) {}));
    return reference;
  }

  /// Immutable pending attempts are projected into the Conversation without
  /// claiming they are already accepted or read by remote participants.
  Stream<List<ConversationOutgoing>> watchOutgoing(String conversationId) {
    final query = database.select(database.outboxOperations)
      ..where((row) =>
          row.profileId.equals(profileId) &
          row.owner.equals(owner) &
          row.operationKind.equals(operationKind) &
          row.resourceId.equals(conversationId))
      ..orderBy([(row) => OrderingTerm.asc(row.observedAt)]);
    return query.watch().map((rows) => [
      for (final row in rows)
        if (row.state != OutboxState.cancelled.wireValue)
          _row(row),
    ]);
  }

  ConversationOutgoing _row(OutboxOperation row) {
    final payload = jsonDecode(row.payloadJson) as Map<String, dynamic>;
    final mode = payload['mode']?.toString();
    return ConversationOutgoing(
      reference: row.intentId,
      kind: mode == 'form' ? 'form_request'
          : mode == 'media'
          ? payload['point_kind']?.toString() ?? 'information'
          : mode == 'text' ? 'information'
          : payload['kind']?.toString() ?? 'information',
      title: payload['title']?.toString() ?? '',
      body: payload['body']?.toString() ?? '',
      observedAt: row.observedAt,
      state: row.state,
      mediaKind: payload['media_kind']?.toString(),
      filename: payload['filename']?.toString(),
      localFilePath: payload['local_file_path']?.toString(),
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
    if (conversationId.isEmpty || operation.resourceId != conversationId ||
        !{'text', 'point', 'form', 'media'}.contains(mode)) {
      return OutboxResolution.conflict;
    }
    final Map<String, dynamic> confirmed;
    if (mode == 'media') {
      final localFile = payload['local_file_path']?.toString() ?? '';
      final filename = payload['filename']?.toString() ?? '';
      final kind = payload['media_kind']?.toString() ?? '';
      if (localFile.isEmpty || filename.isEmpty || kind.isEmpty ||
          !await File(localFile).exists()) {
        return OutboxResolution.conflict;
      }
      final response = await api.upload(
        'api/v1/conversations/$conversationId/media/',
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
              ? null : jsonEncode(payload['options']),
          'form_version_id': payload['form_version_id'],
          'questions': payload['questions'] == null
              ? null : jsonEncode(payload['questions']),
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
      if (confirmed['attachment'] is! Map) {
        return OutboxResolution.awaitingConfirmation;
      }
    } else {
      final endpoint = mode == 'form'
          ? 'api/v1/conversations/$conversationId/forms/'
          : 'api/v1/conversations/$conversationId/compose/';
      final data = Map<String, dynamic>.from(payload)
        ..remove('conversation_id');
      final response = await api.post(endpoint, body: data);
      confirmed = response.jsonObject();
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
).hasMatch(suffix)
              && suffix.length <= 11
          ? suffix : '.bin';
      stagedPath = '${folder.path}/$reference$extension';
      await original.copy(stagedPath);
    }
    final deviceId = await tokens.deviceInstanceId();
    final request = <String, dynamic>{
      'conversation_id': conversationId,
      'mode': mode,
      'client_reference': reference,
      if (kind != null) 'kind': kind,
      if (body != null) 'body': body,
      if (title != null) 'title': title,
      if (options != null) 'options': options,
      if (formVersionId != null) 'form_version_id': formVersionId,
      if (questions != null) 'questions': questions,
      if (pointId != null) 'point_id': pointId,
      if (audienceId != null) 'audience_id': audienceId,
      if (representedSpaceId != null) 'represented_space_id': representedSpaceId,
      if (stagedPath != null) 'local_file_path': stagedPath,
      if (filename != null) 'filename': filename,
      if (mediaKind != null) 'media_kind': mediaKind,
      if (pointKind != null) 'point_kind': pointKind,
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
        try { await File(stagedPath).delete(); } on Object {}
      }
      rethrow;
    }
    final dispatch = requestDispatch;
    if (dispatch != null) unawaited(dispatch().catchError((Object _) {}));
    return reference;
  }

  /// Immutable pending attempts are projected into the Conversation without
  /// claiming they are already accepted or read by remote participants.
  Stream<List<ConversationOutgoing>> watchOutgoing(String conversationId) {
    final query = database.select(database.outboxOperations)
      ..where((row) =>
          row.profileId.equals(profileId) &
          row.owner.equals(owner) &
          row.operationKind.equals(operationKind) &
          row.resourceId.equals(conversationId))
      ..orderBy([(row) => OrderingTerm.asc(row.observedAt)]);
    return query.watch().map((rows) => [
      for (final row in rows)
        if (row.state != OutboxState.cancelled.wireValue)
          _row(row),
    ]);
  }

  ConversationOutgoing _row(OutboxOperation row) {
    final payload = jsonDecode(row.payloadJson) as Map<String, dynamic>;
    final mode = payload['mode']?.toString();
    return ConversationOutgoing(
      reference: row.intentId,
      kind: mode == 'form' ? 'form_request'
          : mode == 'media'
          ? payload['point_kind']?.toString() ?? 'information'
          : mode == 'text' ? 'information'
          : payload['kind']?.toString() ?? 'information',
      title: payload['title']?.toString() ?? '',
      body: payload['body']?.toString() ?? '',
      observedAt: row.observedAt,
      state: row.state,
      mediaKind: payload['media_kind']?.toString(),
      filename: payload['filename']?.toString(),
      localFilePath: payload['local_file_path']?.toString(),
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
    if (conversationId.isEmpty || operation.resourceId != conversationId ||
        !{'text', 'point', 'form', 'media'}.contains(mode)) {
      return OutboxResolution.conflict;
    }
    final Map<String, dynamic> confirmed;
    if (mode == 'media') {
      final localFile = payload['local_file_path']?.toString() ?? '';
      final filename = payload['filename']?.toString() ?? '';
      final kind = payload['media_kind']?.toString() ?? '';
      if (localFile.isEmpty || filename.isEmpty || kind.isEmpty ||
          !await File(localFile).exists()) {
        return OutboxResolution.conflict;
      }
      final response = await api.upload(
        'api/v1/conversations/$conversationId/media/',
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
              ? null : jsonEncode(payload['options']),
          'form_version_id': payload['form_version_id'],
          'questions': payload['questions'] == null
              ? null : jsonEncode(payload['questions']),
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
      if (confirmed['attachment'] is! Map) {
        return OutboxResolution.awaitingConfirmation;
      }
    } else {
      final endpoint = mode == 'form'
          ? 'api/v1/conversations/$conversationId/forms/'
          : 'api/v1/conversations/$conversationId/compose/';
      final data = Map<String, dynamic>.from(payload)
        ..remove('conversation_id');
      final response = await api.post(endpoint, body: data);
      confirmed = response.jsonObject();
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
