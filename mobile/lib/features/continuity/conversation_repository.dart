import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

import '../../network/makolo_api_client.dart';

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
  static const detailProjectionKind = 'conversation.detail';
  static const invitationsProjectionKind = 'conversation.invitations';
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

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

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

  SyncSourceDefinition detailSource(String id, {String? focusPointId}) => SyncSourceDefinition(
    sourceKey: 'conversation:$id',
    owner: 'Conversations',
    path: 'api/v1/conversations/$id/${focusPointId == null ? '' : '?focus_point=${Uri.encodeQueryComponent(focusPointId)}'}',
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
    await engine.refreshSource(detailSource(id, focusPointId: focusPointId));
  }

  Future<List<Map<String, dynamic>>> searchConversations(String query) async {
    final term = query.trim();
    if (term.isEmpty) return const [];
    final engine = sync;
    if (engine == null) {
      throw StateError('La recherche distante est indisponible.');
    }
    final response = await engine.api.get(
      'api/v1/conversations/?limit=50&q=${Uri.encodeQueryComponent(term)}',
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
      'direct', 'space', 'group', 'activity', 'occurrence',
      'journey', 'dossier', 'project', 'action_proposal',
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
      'space', 'group', 'activity', 'occurrence', 'journey',
      'dossier', 'project', 'action_proposal', 'direct',
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
    if (engine == null) throw StateError('Connexion nécessaire pour demander un formulaire.');
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
    if (engine == null) throw StateError('Connexion nécessaire pour envoyer une pièce.');
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
        MakoloUploadFile(
          fieldName: 'file', path: filePath, filename: filename,
        ),
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
    if (engine == null) throw StateError('Connexion nécessaire pour ouvrir cet échange.');
    final query = '?limit=$limit${cursor == null ? '' : '&cursor=${Uri.encodeQueryComponent(cursor)}'}';
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
    if (engine == null) throw StateError('Connexion nécessaire pour consulter cette pièce.');
    if (!RegExp(r'^[0-9a-fA-F-]{36}
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
    await engine.api.post(
      'api/v1/conversations/points/$pointId/respond/',
      body: {
        'value': value,
        'client_reference': clientReference,
        'represented_space_id': ?representedSpaceId,
      },
    );
    await refreshDetail(conversationId);
    await refreshList();
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
    await engine.api.post('api/v1/conversations/points/$pointId/acknowledge/');
    await refreshDetail(conversationId);
    await refreshList();
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
    await refreshInvitations();
    await refreshList();
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
    await engine.api.post(
      'api/v1/conversations/$conversationId/personal-state/',
      body: {
        'mute': ?mute,
        'hidden': ?hidden,
        'archived': ?archived,
        'pinned': ?pinned,
        'revisit': ?revisit,
      },
    );
    await refreshDetail(conversationId);
    await refreshList();
  }
}
).hasMatch(attachmentId)) {
      throw const FormatException('Invalid Attachment identity.');
    }
    final basename = filename.split(RegExp(r'[/\\]')).last;
    final dot = basename.lastIndexOf('.');
    final extension = dot < 0 ? '.bin' : basename.substring(dot);
    final safeExtension = RegExp(r'^\.[A-Za-z0-9]{1,9}
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
    await engine.api.post(
      'api/v1/conversations/points/$pointId/respond/',
      body: {
        'value': value,
        'client_reference': clientReference,
        'represented_space_id': ?representedSpaceId,
      },
    );
    await refreshDetail(conversationId);
    await refreshList();
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
    await engine.api.post('api/v1/conversations/points/$pointId/acknowledge/');
    await refreshDetail(conversationId);
    await refreshList();
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
    await refreshInvitations();
    await refreshList();
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
    await engine.api.post(
      'api/v1/conversations/$conversationId/personal-state/',
      body: {
        'mute': ?mute,
        'hidden': ?hidden,
        'archived': ?archived,
        'pinned': ?pinned,
        'revisit': ?revisit,
      },
    );
    await refreshDetail(conversationId);
    await refreshList();
  }
}
).hasMatch(extension)
        ? extension
        : '.bin';
    final temp = await getTemporaryDirectory();
    final safeProfile = profileId.replaceAll(RegExp('[^A-Za-z0-9_-]'), '_');
    final folder = Directory('${temp.path}/conversation-$safeProfile');
    await folder.create(recursive: true);
    final destination = File('${folder.path}/$attachmentId$safeExtension');
    await engine.api.download(
      'api/v1/conversations/attachments/$attachmentId/download/',
      destinationPath: destination.path,
    );
    return destination;
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
    await engine.api.post(
      'api/v1/conversations/points/$pointId/respond/',
      body: {
        'value': value,
        'client_reference': clientReference,
        'represented_space_id': ?representedSpaceId,
      },
    );
    await refreshDetail(conversationId);
    await refreshList();
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
    await engine.api.post('api/v1/conversations/points/$pointId/acknowledge/');
    await refreshDetail(conversationId);
    await refreshList();
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
    await refreshInvitations();
    await refreshList();
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
    await engine.api.post(
      'api/v1/conversations/$conversationId/personal-state/',
      body: {
        'mute': ?mute,
        'hidden': ?hidden,
        'archived': ?archived,
        'pinned': ?pinned,
        'revisit': ?revisit,
      },
    );
    await refreshDetail(conversationId);
    await refreshList();
  }
}
