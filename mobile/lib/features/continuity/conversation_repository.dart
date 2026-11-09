import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:path_provider/path_provider.dart';

import 'conversation_local_delivery.dart';

import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class ConversationRepository {
  ConversationRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const listProjectionKind = 'conversation.list';
  static const archivedProjectionKind = 'conversation.archived';
  static const detailProjectionKind = 'conversation.detail';
  static const invitationsProjectionKind = 'conversation.invitations';
  static const depthProjectionKind = 'conversation.point.depth';
  static const listFreshness = FreshnessPolicy(
    id: 'conversation-list-contextual',
    refreshRecommendedAfter: Duration(minutes: 15),
    usableButOldAfter: Duration(days: 2),
  );
  static const detailFreshness = FreshnessPolicy(
    id: 'conversation-detail-contextual',
    refreshRecommendedAfter: Duration(minutes: 10),
    usableButOldAfter: Duration(days: 2),
  );
  static const invitationsFreshness = FreshnessPolicy(
    id: 'conversation-invitations-contextual',
    refreshRecommendedAfter: Duration(minutes: 10),
    usableButOldAfter: Duration(hours: 12),
  );

  /// Covers in the list are restricted to public, same-origin owner media.
  /// Private Conversation attachments are never loaded through Image.network.
  Uri? publicContextImageUri(String? ownerPath) {
    final raw = ownerPath?.trim();
    if (raw == null || !raw.startsWith('/') || raw.startsWith('//')) {
      return null;
    }
    final parsed = Uri.tryParse(raw);
    final origin = sync?.api.baseUri;
    if (parsed == null ||
        origin == null ||
        parsed.hasScheme ||
        parsed.hasAuthority ||
        parsed.query.isNotEmpty ||
        parsed.fragment.isNotEmpty) {
      return null;
    }
    final resolved = origin.resolveUri(parsed);
    if (resolved.host != origin.host ||
        resolved.scheme != origin.scheme ||
        resolved.port != origin.port) {
      return null;
    }
    return resolved;
  }

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  // Injected by the authenticated runtime; no second domain store.
  ConversationLocalDelivery? delivery;

  SyncSourceDefinition listSource() => SyncSourceDefinition(
    sourceKey: 'conversations',
    owner: 'Conversations',
    path: 'api/v1/conversations/?limit=50',
    projectionKind: listProjectionKind,
    category: SyncSourceCategory.collection,
    freshnessPolicy: listFreshness,
    parser: (response) {
      final payload = response.jsonObject();
      if (payload['results'] is! List || payload['count'] is! num) {
        throw const FormatException(
          'Expected Conversations owner collection contract.',
        );
      }
      return AcquiredProjection(schemaVersion: 1, payload: payload);
    },
    applier: applyProjectionSnapshot,
  );

  SyncSourceDefinition archivedSource() => SyncSourceDefinition(
    sourceKey: 'conversation-archives',
    owner: 'Conversations',
    path: 'api/v1/conversations/?limit=50&tab=archived',
    projectionKind: archivedProjectionKind,
    category: SyncSourceCategory.collection,
    freshnessPolicy: listFreshness,
    parser: (response) {
      final payload = response.jsonObject();
      if (payload['results'] is! List || payload['count'] is! num) {
        throw const FormatException(
          'Expected archived Conversations owner list.',
        );
      }
      return AcquiredProjection(schemaVersion: 1, payload: payload);
    },
    applier: applyProjectionSnapshot,
  );

  SyncSourceDefinition invitationsSource() => SyncSourceDefinition(
    sourceKey: 'conversation-invitations',
    owner: 'Conversations',
    path: 'api/v1/conversations/invitations/?limit=50',
    projectionKind: invitationsProjectionKind,
    category: SyncSourceCategory.collection,
    freshnessPolicy: invitationsFreshness,
    parser: (response) {
      final payload = response.jsonObject();
      if (payload['results'] is! List || payload['count'] is! num) {
        throw const FormatException(
          'Expected Conversation invitations owner collection contract.',
        );
      }
      return AcquiredProjection(schemaVersion: 1, payload: payload);
    },
    applier: applyProjectionSnapshot,
  );

  SyncSourceDefinition detailSource(
    String id, {
    String? focusPointId,
  }) => SyncSourceDefinition(
    sourceKey: 'conversation:$id',
    owner: 'Conversations',
    path:
        'api/v1/conversations/$id/${focusPointId == null ? '' : '?focus_point=${Uri.encodeQueryComponent(focusPointId)}'}',
    projectionKind: detailProjectionKind,
    resourceKey: id,
    category: SyncSourceCategory.keyedDetail,
    freshnessPolicy: detailFreshness,
    parser: (response) {
      final payload = response.jsonObject();
      if (payload['id']?.toString() != id || payload['points'] is! List) {
        throw const FormatException(
          'Expected Conversations owner detail contract.',
        );
      }
      return AcquiredProjection(
        schemaVersion: 1,
        payload: jsonDecode(jsonEncode(payload)) as Map<String, dynamic>,
      );
    },
    applier: applyProjectionSnapshot,
  );

  Stream<StoredProjection?> watchArchived() =>
      store.watchProjection(archivedProjectionKind);
  Future<StoredProjection?> readArchived() =>
      store.readProjection(archivedProjectionKind);

  Stream<StoredProjection?> watchList() =>
      store.watchProjection(listProjectionKind);

  Future<StoredProjection?> readList() =>
      store.readProjection(listProjectionKind);

  Stream<StoredProjection?> watchInvitations() =>
      store.watchProjection(invitationsProjectionKind);

  Future<StoredProjection?> readInvitations() =>
      store.readProjection(invitationsProjectionKind);

  Stream<StoredProjection?> watchDetail(String id) =>
      store.watchProjection(detailProjectionKind, resourceKey: id);

  Future<StoredProjection?> readDetail(String id) =>
      store.readProjection(detailProjectionKind, resourceKey: id);

  Stream<OwnerSourceState> watchListSource() => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'conversations',
  );

  Future<OwnerSourceState> readListSource() => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'conversations',
  );

  Stream<OwnerSourceState> watchInvitationsSource() => watchOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'conversation-invitations',
  );

  Future<OwnerSourceState> readInvitationsSource() => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'conversation-invitations',
  );

  Stream<OwnerSourceState> watchDetailSource(String id) =>
      watchOwnerSourceState(
        database: database,
        profileId: profileId,
        sourceKey: 'conversation:$id',
      );

  Future<OwnerSourceState> readDetailSource(String id) => readOwnerSourceState(
    database: database,
    profileId: profileId,
    sourceKey: 'conversation:$id',
  );

  Future<void> refreshList() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    await engine.refreshSource(listSource());
  }

  Future<void> refreshArchived() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    await engine.refreshSource(archivedSource());
  }

  Future<void> refreshInvitations() async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    await engine.refreshSource(invitationsSource());
  }

  Future<void> refreshDetail(String id, {String? focusPointId}) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    try {
      await engine.refreshSource(detailSource(id, focusPointId: focusPointId));
    } on MakoloApiError catch (error) {
      if (error.statusCode == 403 || error.statusCode == 404) {
        await store.deleteProjection(detailProjectionKind, resourceKey: id);
        await store.deleteProjection(depthProjectionKind, resourceKey: id);
      }
      rethrow;
    }
  }

  Future<StoredProjection?> readPointDepth(String conversationId) =>
      store.readProjection(depthProjectionKind, resourceKey: conversationId);

  Future<Map<String, dynamic>> pointDepth({
    required String conversationId,
    String section = 'history',
    String query = '',
    String? cursor,
    int limit = 25,
  }) async {
    if (!{'history', 'all', 'active'}.contains(section) ||
        limit < 1 ||
        limit > 60) {
      throw ArgumentError('Invalid Point depth selector.');
    }
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour consulter cet historique.');
    }
    final params = <String, String>{
      'section': section,
      'limit': '$limit',
      if (query.trim().isNotEmpty) 'q': query.trim(),
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
    };
    final uri = Uri(
      path: 'api/v1/conversations/$conversationId/points/',
      queryParameters: params,
    );
    try {
      final response = await engine.api.get(uri.toString());
      final payload = response.jsonObject();
      if (payload['results'] is! List || !payload.containsKey('next_cursor')) {
        throw const FormatException('Expected C5 Conversation Point history.');
      }
      if (cursor == null && section == 'history' && query.trim().isEmpty) {
        final now = DateTime.now().toUtc();
        try {
          await store.putProjection(
            kind: depthProjectionKind,
            resourceKey: conversationId,
            schemaVersion: 1,
            payload: payload,
            receivedAt: now,
            freshUntil: now.add(const Duration(minutes: 15)),
            expiresAt: now.add(const Duration(hours: 12)),
            freshnessPolicyId: 'conversation-depth-owner',
          );
        } on Object {
          // Owner-confirmed search results still render if local storage fails.
        }
      }
      return payload;
    } on MakoloApiError catch (error) {
      if (error.statusCode == 403 || error.statusCode == 404) {
        await store.deleteProjection(
          depthProjectionKind,
          resourceKey: conversationId,
        );
        await store.deleteProjection(
          detailProjectionKind,
          resourceKey: conversationId,
        );
      }
      rethrow;
    }
  }

  Future<List<Map<String, dynamic>>> searchConversations(
    String query, {
    String tab = 'all',
  }) async {
    final term = query.trim();
    if (term.isEmpty) return const [];
    final engine = sync;
    if (engine == null) {
      throw StateError('La recherche distante est indisponible.');
    }
    final response = await engine.api.get(
      'api/v1/conversations/?limit=50&q=${Uri.encodeQueryComponent(term)}'
      '${tab == 'archived' ? '&tab=archived' : ''}',
    );
    final payload = response.jsonObject();
    if (payload['results'] is! List) {
      throw const FormatException('Expected Conversations search results.');
    }
    return (payload['results'] as List)
        .whereType<Map>()
        .map((row) => row.map((key, value) => MapEntry(key.toString(), value)))
        .toList(growable: false);
  }

  Future<List<Map<String, dynamic>>> conversationsForContext({
    required String kind,
    required String id,
  }) async {
    const allowed = {
      'direct',
      'space',
      'group',
      'activity',
      'occurrence',
      'journey',
      'dossier',
      'project',
      'action_proposal',
    };
    if (!allowed.contains(kind) || id.isEmpty) return const [];
    final engine = sync;
    if (engine == null) return const [];
    final response = await engine.api.get(
      'api/v1/conversations/by-context/$kind/${Uri.encodeComponent(id)}/',
    );
    final payload = response.jsonObject();
    if (payload['results'] is! List) {
      throw const FormatException('Expected contextual Conversations.');
    }
    return (payload['results'] as List)
        .whereType<Map>()
        .map((row) => row.map((key, value) => MapEntry(key.toString(), value)))
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> contextDecision({
    required String kind,
    required String id,
  }) async {
    const allowed = {
      'space',
      'group',
      'activity',
      'occurrence',
      'journey',
      'dossier',
      'project',
      'action_proposal',
      'direct',
    };
    if (!allowed.contains(kind) || id.isEmpty) {
      return {'results': <Object>[], 'can_ensure': false};
    }
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion indisponible.');
    }
    final response = await engine.api.get(
      'api/v1/conversations/by-context/$kind/${Uri.encodeComponent(id)}/',
    );
    return response.jsonObject();
  }

  Future<String> ensureContext({
    required String kind,
    required String id,
  }) async {
    if (kind == 'direct') {
      throw StateError('Le contact direct exige un consentement existant.');
    }
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    final result = await engine.api.post(
      'api/v1/conversations/by-context/$kind/${Uri.encodeComponent(id)}/ensure/',
    );
    final conversationId = result.jsonObject()['id']?.toString();
    if (conversationId == null || conversationId.isEmpty) {
      throw const FormatException('Conversation identity not returned.');
    }
    await refreshList();
    return conversationId;
  }

  Future<String> compose({
    required String conversationId,
    required String clientReference,
    required String mode,
    String? kind,
    String? body,
    String? title,
    List<String>? options,
    bool multipleChoice = false,
    String? audienceId,
    String? pointId,
    String? representedSpaceId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour publier.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/compose/',
      body: {
        'mode': mode,
        'client_reference': clientReference,
        'kind': ?kind,
        'body': ?body,
        'title': ?title,
        'options': ?options,
        'multiple_choice': multipleChoice,
        'audience_id': ?audienceId,
        'point_id': ?pointId,
        'represented_space_id': ?representedSpaceId,
      },
    );
    final pointIdReturned = response.jsonObject()['point_id']?.toString();
    if (pointIdReturned == null || pointIdReturned.isEmpty) {
      throw const FormatException('Published Point identity not returned.');
    }
    // A Point/Exchange already confirmed by the owner remains successful
    // even when its next projection acquisition fails.
    await _refreshPublished(conversationId);
    return pointIdReturned;
  }

  Future<String> publishForm({
    required String conversationId,
    required String title,
    required String clientReference,
    String? formVersionId,
    List<String>? questions,
    String? audienceId,
    String? representedSpaceId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour demander un formulaire.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/forms/',
      body: {
        'title': title,
        'client_reference': clientReference,
        'form_version_id': ?formVersionId,
        'questions': ?questions,
        'audience_id': ?audienceId,
        'represented_space_id': ?representedSpaceId,
      },
    );
    final pointId = response.jsonObject()['point_id']?.toString();
    if (pointId == null || pointId.isEmpty) {
      throw const FormatException('Form Point identity not returned.');
    }
    await _refreshPublished(conversationId);
    return pointId;
  }

  static String mediaMime(String name, String kind) {
    final lower = name.toLowerCase();
    if (kind == 'voice' || kind == 'audio') {
      if (lower.endsWith('.webm')) return 'audio/webm';
      if (lower.endsWith('.ogg')) return 'audio/ogg';
      if (lower.endsWith('.mp3')) return 'audio/mpeg';
      if (lower.endsWith('.wav')) return 'audio/wav';
      return 'audio/mp4';
    }
    if (kind == 'image') {
      return lower.endsWith('.png') ? 'image/png' : 'image/jpeg';
    }
    if (kind == 'video') {
      return lower.endsWith('.webm') ? 'video/webm' : 'video/mp4';
    }
    if (lower.endsWith('.pdf')) return 'application/pdf';
    if (lower.endsWith('.docx')) {
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    }
    if (lower.endsWith('.doc')) return 'application/msword';
    if (lower.endsWith('.txt')) return 'text/plain';
    return 'application/octet-stream';
  }

  Future<Map<String, dynamic>> uploadMedia({
    required String conversationId,
    required String filePath,
    required String filename,
    required String kind,
    required String clientReference,
    String? caption,
    String? pointId,
    String? audienceId,
    String? representedSpaceId,
    TransferProgress? onProgress,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour envoyer une pièce.');
    }
    final response = await engine.api.upload(
      'api/v1/conversations/$conversationId/media/',
      fields: {
        'client_reference': clientReference,
        'kind': kind,
        'mime_type': mediaMime(filename, kind),
        'body': caption ?? '',
        'point_id': pointId,
        'audience_id': audienceId,
        'represented_space_id': representedSpaceId,
      },
      files: [
        MakoloUploadFile(fieldName: 'file', path: filePath, filename: filename),
      ],
      onProgress: onProgress,
    );
    final payload = response.jsonObject();
    if (payload['point_id']?.toString().isEmpty != false ||
        payload['attachment'] is! Map) {
      throw const FormatException('Attachment identity not returned.');
    }
    await _refreshPublished(conversationId);
    return payload;
  }

  /// Publish one semantic Point with all its authorized media in a single
  /// server transaction. Unlike a text-only Point, media bytes require an
  /// active transfer; the caller keeps the draft if this cannot finish.
  Future<String> publishSemanticPointWithMedia({
    required String conversationId,
    required String clientReference,
    required String kind,
    required String title,
    required String body,
    required List<String> options,
    required bool multipleChoice,
    required List<Map<String, dynamic>> media,
    String? audienceId,
    String? representedSpaceId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour envoyer ces médias.');
    }
    if (media.isEmpty || media.length > 24) {
      throw const FormatException('Nombre de médias invalide.');
    }
    final manifest = <Map<String, dynamic>>[];
    final files = <MakoloUploadFile>[];
    for (var i = 0; i < media.length; i++) {
      final item = media[i];
      final path = item['path']?.toString() ?? '';
      final filename = item['filename']?.toString() ?? '';
      final mediaKind = item['kind']?.toString() ?? '';
      if (path.isEmpty || filename.isEmpty) {
        throw const FormatException('Pièce jointe incomplète.');
      }
      final field = 'media_$i';
      manifest.add({
        'field': field,
        'scope': item['scope'],
        if (item['scope'] == 'option') 'option_index': item['option_index'],
        'kind': mediaKind,
        'caption': item['caption']?.toString() ?? '',
        'mime_type': mediaMime(filename, mediaKind),
      });
      files.add(
        MakoloUploadFile(fieldName: field, path: path, filename: filename),
      );
    }
    final response = await engine.api.upload(
      'api/v1/conversations/$conversationId/semantic-media/',
      fields: {
        'client_reference': clientReference,
        'kind': kind,
        'title': title,
        'body': body,
        'options': jsonEncode(options),
        'multiple_choice': multipleChoice ? 'true' : 'false',
        'media_manifest': jsonEncode(manifest),
        'audience_id': audienceId,
        'represented_space_id': representedSpaceId,
      },
      files: files,
    );
    final payload = response.jsonObject();
    final pointId = payload['point_id']?.toString() ?? '';
    if (pointId.isEmpty || payload['attachments'] is! List) {
      throw const FormatException('Point ou médias non confirmés.');
    }
    await _refreshPublished(conversationId);
    return pointId;
  }

  Future<Map<String, dynamic>> respondWithMedia({
    required String conversationId,
    required String pointId,
    required String filePath,
    required String filename,
    required String kind,
    required String clientReference,
    String? representedSpaceId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour répondre avec un fichier.');
    }
    final response = await engine.api.upload(
      'api/v1/conversations/points/$pointId/reply-media/',
      fields: {
        'client_reference': clientReference,
        'kind': kind,
        'mime_type': mediaMime(filename, kind),
        'represented_space_id': representedSpaceId,
      },
      files: [
        MakoloUploadFile(fieldName: 'file', path: filePath, filename: filename),
      ],
    );
    final payload = response.jsonObject();
    if (payload['point_id']?.toString() != pointId ||
        payload['response_id'] == null ||
        payload['attachment'] is! Map) {
      throw const FormatException('Media response confirmation is incomplete.');
    }
    await _refreshPublished(conversationId);
    return payload;
  }

  Future<void> _refreshPublished(String id) async {
    // The mutation is owner-confirmed already. A later projection refresh
    // failure must not turn success into an erroneous retry prompt.
    try {
      await refreshDetail(id);
    } on Object {
      // Local snapshot stays available until the next owner acquisition.
    }
    try {
      await refreshList();
    } on Object {
      // The confirmed mutation is not rolled back by a transport incident.
    }
  }

  Future<Map<String, dynamic>> exchangeEntries({
    required String pointId,
    String? cursor,
    int limit = 25,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour ouvrir cet échange.');
    }
    final query =
        '?limit=$limit${cursor == null ? '' : '&cursor=${Uri.encodeQueryComponent(cursor)}'}';
    final response = await engine.api.get(
      'api/v1/conversations/points/$pointId/entries/$query',
    );
    final payload = response.jsonObject();
    if (payload['results'] is! List) {
      throw const FormatException('Expected Exchange owner collection.');
    }
    return payload;
  }

  Future<File> downloadAttachment({
    required String attachmentId,
    required String filename,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion nécessaire pour consulter cette pièce.');
    }
    if (!RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(attachmentId)) {
      throw const FormatException('Invalid Attachment identity.');
    }
    final basename = filename.split(RegExp(r'[/\\]')).last;
    final dot = basename.lastIndexOf('.');
    final extension = dot < 0 ? '.bin' : basename.substring(dot);
    final safeExtension = RegExp(r'^\.[A-Za-z0-9]{1,9}$').hasMatch(extension)
        ? extension
        : '.bin';
    final temp = await getTemporaryDirectory();
    final safeProfile = profileId.replaceAll(RegExp('[^A-Za-z0-9_-]'), '_');
    final folder = Directory('${temp.path}/conversation-$safeProfile');
    await folder.create(recursive: true);
    // Each viewer owns its temporary copy. Inline previews and the detailed
    // gallery must never delete each other's files on disposal.
    final nonce = Random.secure().nextInt(0x7fffffff).toRadixString(16);
    final destination = File(
      '${folder.path}/$attachmentId-${DateTime.now().microsecondsSinceEpoch}-$nonce$safeExtension',
    );
    try {
      await engine.api.download(
        'api/v1/conversations/attachments/$attachmentId/download/',
        destinationPath: destination.path,
      );
      return destination;
    } on Object {
      if (await destination.exists()) await destination.delete();
      rethrow;
    }
  }

  Future<void> respondToPoint({
    required String conversationId,
    required String pointId,
    required Object? value,
    required String clientReference,
    String? representedSpaceId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour envoyer cette réponse.',
      );
    }
    final response = await engine.api.post(
      'api/v1/conversations/points/$pointId/respond/',
      body: {
        'value': value,
        'client_reference': clientReference,
        'represented_space_id': ?representedSpaceId,
      },
    );
    final payload = response.jsonObject();
    if (payload['point_id']?.toString() != pointId ||
        payload['id'] == null ||
        payload['status'] != 'active') {
      throw const FormatException('Réponse non confirmée par Conversations.');
    }
    await _refreshPublished(conversationId);
  }

  Future<void> acknowledgePoint({
    required String conversationId,
    required String pointId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour confirmer la lecture.',
      );
    }
    final response = await engine.api.post(
      'api/v1/conversations/points/$pointId/acknowledge/',
    );
    final confirmed = response.jsonObject();
    if (confirmed['point_id']?.toString() != pointId ||
        confirmed['acknowledged_at'] == null) {
      throw const FormatException('Prise de connaissance non confirmée.');
    }
    await _refreshPublished(conversationId);
  }

  Future<void> closePointResponses({
    required String conversationId,
    required String pointId,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Une connexion est nécessaire pour clore les réponses.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/points/$pointId/close-responses/',
    );
    final payload = response.jsonObject();
    if (payload['point_id']?.toString() != pointId ||
        !{'response_closed', 'resolved'}.contains(payload['lifecycle'])) {
      throw const FormatException('Clôture non confirmée par Conversations.');
    }
    await _refreshPublished(conversationId);
  }

  Future<void> resolvePoint({
    required String conversationId,
    required String pointId,
    required String summary,
    List<String> selectedOptionIds = const [],
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Une connexion est nécessaire pour résoudre le Point.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/points/$pointId/resolve/',
      body: {
        'summary': summary.trim(),
        'selected_option_ids': selectedOptionIds,
      },
    );
    final payload = response.jsonObject();
    if (payload['point_id']?.toString() != pointId ||
        payload['lifecycle'] != 'resolved' ||
        payload['resolution_id'] == null) {
      throw const FormatException(
        'Résolution non confirmée par Conversations.',
      );
    }
    await _refreshPublished(conversationId);
  }

  Future<List<Map<String, dynamic>>> searchInvitationCandidates({
    required String conversationId,
    required String query,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion requise pour rechercher.');
    if (query.trim().length < 2) return const [];
    final response = await engine.api.get(
      'api/v1/conversations/$conversationId/candidates/'
      '?q=${Uri.encodeQueryComponent(query.trim())}',
    );
    final rows = response.jsonObject()['results'];
    return rows is List
        ? [
            for (final row in rows)
              if (row is Map)
                row.map((key, value) => MapEntry(key.toString(), value)),
          ]
        : const [];
  }

  Future<Map<String, dynamic>> inviteIdentifier({
    required String conversationId,
    required String kind,
    required String identifier,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion requise pour inviter.');
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/invite/',
      body: {'kind': kind, 'identifier': identifier.trim()},
    );
    final result = response.jsonObject();
    if (result['id'] == null || result['status'] == null) {
      throw const FormatException('Invitation non confirmée.');
    }
    try {
      await refreshDetail(conversationId);
    } on Object {
      // The owner has confirmed the invitation; cache refresh is optional.
    }
    return result;
  }

  Future<void> manageConversationParticipant({
    required String conversationId,
    required String operation,
    required String resourceId,
  }) async {
    final engine = sync;
    if (engine == null)
      throw StateError('Connexion requise pour modifier les participants.');
    final route = switch (operation) {
      'remove' => 'participants/$resourceId/remove/',
      'cancel' => 'invitations/$resourceId/cancel/',
      'revoke' => 'collectives/$resourceId/revoke/',
      _ => throw ArgumentError.value(operation, 'operation'),
    };
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/$route',
    );
    if (response.jsonObject()['status'] == null) {
      throw const FormatException(
        'Modification de participation non confirmée.',
      );
    }
    try {
      await refreshDetail(conversationId);
    } on Object {
      // Confirmed removal can itself revoke this Profile's access.
    }
  }

  Future<void> decideCollectiveInvitation({
    required String accessId,
    required bool accept,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion requise pour répondre.');
    final response = await engine.api.post(
      'api/v1/conversations/collective-invitations/$accessId/respond/',
      body: {'decision': accept ? 'accept' : 'decline'},
    );
    if (response.jsonObject()['status'] == null) {
      throw const FormatException('Décision non confirmée.');
    }
    try {
      await refreshInvitations();
    } on Object {
      /* Owner will reconcile. */
    }
    try {
      await refreshList();
    } on Object {
      /* Owner will reconcile. */
    }
  }

  Future<void> decideJoinRequest({
    required String conversationId,
    required String requestId,
    required bool approve,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion requise pour répondre.');
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/join-requests/$requestId/decide/',
      body: {'decision': approve ? 'approve' : 'reject'},
    );
    if (response.jsonObject()['status'] == null) {
      throw const FormatException('Décision non confirmée.');
    }
    try {
      await refreshDetail(conversationId);
    } on Object {
      // Keep the confirmed decision, allow next owner acquisition.
    }
  }

  Future<List<Map<String, dynamic>>> conversationJoinRequests(String id) async {
    final engine = sync;
    if (engine == null)
      throw StateError('Connexion requise pour voir les demandes.');
    final response = await engine.api.get(
      'api/v1/conversations/$id/join-requests/',
    );
    final rows = response.jsonObject()['results'];
    return rows is List
        ? [
            for (final row in rows)
              if (row is Map)
                row.map((key, value) => MapEntry(key.toString(), value)),
          ]
        : const [];
  }

  Future<void> conversationSelfEntry({
    required String conversationId,
    required String action,
  }) async {
    final engine = sync;
    if (engine == null)
      throw StateError('Connexion requise pour changer de participation.');
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/entry/',
      body: {'action': action},
    );
    if (response.jsonObject()['status'] == null) {
      throw const FormatException('État de participation non confirmé.');
    }
    try {
      await refreshDetail(conversationId);
    } on Object {
      // Leaving can legitimately revoke the current viewer's detail.
    }
  }

  Future<String?> respondToInvitation({
    required String invitationId,
    required bool accept,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError(
        'Une connexion est nécessaire pour répondre à cette invitation.',
      );
    }
    final response = await engine.api.post(
      'api/v1/conversations/invitations/$invitationId/respond/',
      body: {'decision': accept ? 'accept' : 'decline'},
    );
    final payload = response.jsonObject();
    try {
      final prior = await readInvitations();
      if (prior != null && payload['status'] != 'pending') {
        final entries = (prior.payload['results'] as List? ?? [])
            .where(
              (entry) =>
                  entry is Map && entry['id']?.toString() != invitationId,
            )
            .toList(growable: false);
        await store.putProjection(
          kind: invitationsProjectionKind,
          schemaVersion: prior.schemaVersion,
          payload: {
            ...prior.payload,
            'results': entries,
            'count': entries.length,
          },
          receivedAt: DateTime.now().toUtc(),
          freshnessPolicyId: invitationsFreshness.id,
          expiresAt: prior.expiresAt,
        );
      }
    } on Object {
      // A failed optional local projection update never negates an owner ACK.
    }
    // The invitation decision is confirmed already. Refresh errors must
    // never turn that success into a second accept/decline attempt.
    try {
      await refreshInvitations();
    } on Object {
      // Next owner acquisition reconciles the invitation list.
    }
    try {
      await refreshList();
    } on Object {
      // Accepted invitation remains confirmed.
    }
    return payload['conversation_id']?.toString();
  }

  Future<void> updatePersonalState({
    required String conversationId,
    bool? mute,
    bool? hidden,
    bool? archived,
    bool? pinned,
    bool? revisit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Une connexion est nécessaire pour modifier cet état.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/personal-state/',
      body: {
        'mute': ?mute,
        'hidden': ?hidden,
        'archived': ?archived,
        'pinned': ?pinned,
        'revisit': ?revisit,
      },
    );
    try {
      final confirmed = response.jsonObject();
      final prior = await readDetail(conversationId);
      if (prior != null) {
        await store.putProjection(
          kind: detailProjectionKind,
          resourceKey: conversationId,
          schemaVersion: prior.schemaVersion,
          payload: {
            ...prior.payload,
            'personal_state': {
              'muted': confirmed['muted'] == true,
              'hidden': confirmed['hidden'] == true,
              'archived': confirmed['archived'] == true,
              'pinned': confirmed['pinned'] == true,
              'revisit': confirmed['revisit'] == true,
            },
          },
          receivedAt: DateTime.now().toUtc(),
          expiresAt: prior.expiresAt,
          freshnessPolicyId: detailFreshness.id,
        );
      }
      if (confirmed['hidden'] == true || confirmed['archived'] == true) {
        final listing = await readList();
        if (listing != null) {
          final visible = (listing.payload['results'] as List? ?? [])
              .where(
                (item) =>
                    item is Map && item['id']?.toString() != conversationId,
              )
              .toList(growable: false);
          await store.putProjection(
            kind: listProjectionKind,
            schemaVersion: listing.schemaVersion,
            payload: {
              ...listing.payload,
              'results': visible,
              'count': visible.length,
            },
            receivedAt: DateTime.now().toUtc(),
            freshnessPolicyId: listFreshness.id,
            expiresAt: listing.expiresAt,
          );
        }
      }
      if (confirmed['archived'] == false) {
        final archived = await readArchived();
        if (archived != null) {
          final available = (archived.payload['results'] as List? ?? [])
              .where(
                (item) =>
                    item is Map && item['id']?.toString() != conversationId,
              )
              .toList(growable: false);
          await store.putProjection(
            kind: archivedProjectionKind,
            schemaVersion: archived.schemaVersion,
            payload: {
              ...archived.payload,
              'results': available,
              'count': available.length,
            },
            receivedAt: DateTime.now().toUtc(),
            freshnessPolicyId: listFreshness.id,
            expiresAt: archived.expiresAt,
          );
        }
      }
    } on Object {
      // The owner confirms this personal action even if local storage fails.
    }
    await _refreshPublished(conversationId);
    if (archived != null) {
      try {
        await refreshArchived();
      } on Object {
        // Archive projection reconciles during its next acquisition.
      }
    }
  }
}
