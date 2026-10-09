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

  SyncSourceDefinition detailSource(String id) => SyncSourceDefinition(
    sourceKey: 'conversation:$id',
    owner: 'Conversations',
    path: 'api/v1/conversations/$id/',
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

  Future<void> refreshDetail(String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Conversations owner is not configured.');
    }
    await engine.refreshSource(detailSource(id));
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
