import 'dart:convert';

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
    await refreshDetail(conversationId);
    await refreshList();
    return pointIdReturned;
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
