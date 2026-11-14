import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'dart:math';

import '../../platform/files/native_directories.dart';

import 'conversation_local_delivery.dart';

import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../data/local/conversation_entry_store.dart';
import 'conversation_realtime.dart';
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

  late final exchangeStore = ConversationEntryStore(database, store, profileId);
  ConversationRealtime? _realtime;
  final Map<String, Future<void>> _exchangeRefreshes = {};

  ConversationRealtime? get realtime {
    final engine = sync;
    if (engine == null) return null;
    return _realtime ??= ConversationRealtime(
      api: engine.api,
      profileId: profileId,
      onChanged: refreshExchange,
      onInbox: refreshList,
      onRevoked: exchangeStore.revoke,
    );
  }

  Stream<List<Map<String, dynamic>>> watchExchange(
    String pointId, {
    int limit = 100,
  }) async* {
    final socket = realtime;
    socket?.acquire(pointId);
    try {
      yield* exchangeStore.watch(pointId, limit: limit);
    } finally {
      socket?.release(pointId);
    }
  }

  Future<void> refreshExchange(String pointId) =>
      _exchangeRefreshes.putIfAbsent(
        pointId,
        () => _refreshExchange(pointId).whenComplete(() {
          _exchangeRefreshes.remove(pointId);
        }),
      );

  Future<void> _refreshExchange(String pointId) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    try {
      var more = true;
      while (more) {
        final version = await exchangeStore.version(pointId);
        final response = await engine.api.get(
          'api/v1/conversations/points/$pointId/entries/sync/?after_version=$version&limit=50',
          headers: {'X-Makolo-Profile': profileId},
        );
        final page = response.jsonObject();
        if (page['viewer_profile_id'] != profileId ||
            page['scope'] is! String ||
            page['point_id'] != pointId ||
            page['next_version'] is! int ||
            page['has_more'] is! bool ||
            page['results'] is! List) {
          throw const FormatException('Invalid Exchange synchronization scope');
        }
        final scope = page['scope'] as String;
        final priorScope = await exchangeStore.scope(pointId);
        if (priorScope != scope && (priorScope != null || version > 0)) {
          await database.transaction(() async {
            await exchangeStore.revoke(pointId);
            await exchangeStore.setScope(pointId, scope);
          });
          continue;
        }
        final rows = (page['results'] as List)
            .map((row) => Map<String, dynamic>.from(row as Map))
            .toList();
        final next = page['next_version'] as int;
        more = page['has_more'] as bool;
        if (more && next <= version) {
          throw const FormatException('Exchange delta did not advance');
        }
        await database.transaction(() async {
          await exchangeStore.apply(pointId, rows, nextVersion: next);
          await exchangeStore.setScope(pointId, scope);
        });
      }
      final rows = await exchangeStore.read(pointId, limit: 1);
      if (rows.isNotEmpty) {
        // ACK only after Drift committed the authorized projection and cursor.
        await engine.api.post(
          'api/v1/conversations/points/$pointId/receipts/',
          headers: {'X-Makolo-Profile': profileId},
          body: {
            'delivered_sequence': rows.last['sequence'],
            'read_sequence': 0,
          },
        );
      }
      await refreshExchangeReceipts(pointId);
    } on MakoloApiError catch (error) {
      if ({401, 403, 404}.contains(error.statusCode)) {
        await exchangeStore.revoke(pointId);
      }
      if (error.statusCode == 409) await exchangeStore.revoke(pointId);
      rethrow;
    }
  }

  Future<void> markVisibleExchangeRead(
    String pointId,
    Set<String> visible,
  ) async {
    if (visible.isEmpty) return;
    final engine = sync;
    if (engine == null) return;
    final state = (await engine.api.get(
      'api/v1/conversations/points/$pointId/receipts/',
      headers: {'X-Makolo-Profile': profileId},
    )).jsonObject();
    final read = state['read_sequence'];
    if (read is! int) throw const FormatException('Invalid read watermark');
    var next = read;
    for (final row in await exchangeStore.after(pointId, read)) {
      if (row['own'] != true &&
          row['removed'] != true &&
          !visible.contains(row['id'])) {
        break;
      }
      next = row['sequence'] as int;
    }
    if (next <= read) return;
    final newest = await exchangeStore.read(pointId, limit: 1);
    if (newest.isEmpty) return;
    await engine.api.post(
      'api/v1/conversations/points/$pointId/receipts/',
      headers: {'X-Makolo-Profile': profileId},
      body: {
        'delivered_sequence': newest.last['sequence'],
        'read_sequence': next,
      },
    );
  }

  Future<void> refreshExchangeReceipts(String pointId) async {
    final engine = sync;
    if (engine == null) return;
    final response = await engine.api.get(
      'api/v1/conversations/points/$pointId/receipts/',
      headers: {'X-Makolo-Profile': profileId},
    );
    final receipts = response.jsonObject()['entries'];
    if (receipts is! List) {
      throw const FormatException('Invalid Exchange receipts');
    }
    final rows = await exchangeStore.read(pointId, limit: 100);
    final byId = {
      for (final row in receipts)
        if (row is Map) row['id']: row['delivery'],
    };
    await exchangeStore.apply(pointId, [
      for (final row in rows)
        if (byId.containsKey(row['id'])) {...row, 'delivery': byId[row['id']]},
    ]);
  }

  Future<void> mutateEntry(
    String entryId, {
    String? body,
    int? expectedVersion,
    String? reference,
    List<String>? mentionProfileIds,
    String? emoji,
    bool? selected,
    bool remove = false,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    if (remove) {
      await engine.api.delete(
        'api/v1/conversations/entries/$entryId/',
        headers: {'X-Makolo-Profile': profileId},
      );
    } else if (emoji != null) {
      await engine.api.post(
        'api/v1/conversations/entries/$entryId/reactions/',
        headers: {'X-Makolo-Profile': profileId},
        body: {
          'emoji': emoji,
          'selected': selected,
          'client_reference': reference,
        },
      );
    } else {
      await engine.api.patch(
        'api/v1/conversations/entries/$entryId/',
        headers: {'X-Makolo-Profile': profileId},
        body: {
          'body': body,
          'expected_edit_version': expectedVersion,
          'client_reference': reference,
          'mention_profile_ids': ?mentionProfileIds,
        },
      );
    }
  }

  Future<List<Map<String, dynamic>>> exchangeOptions(
    String pointId, {
    bool references = false,
    String query = '',
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    final route = references
        ? 'references/options/'
        : 'mentions/?q=${Uri.encodeQueryComponent(query)}';
    final response = await engine.api.get(
      'api/v1/conversations/points/$pointId/$route',
      headers: {'X-Makolo-Profile': profileId},
    );
    final result = response.jsonObject()['results'];
    if (result is! List) {
      throw const FormatException('Invalid Exchange options');
    }
    return result.map((row) => Map<String, dynamic>.from(row as Map)).toList();
  }

  Future<Map<String, dynamic>> locateExchangeEntry(
    String pointId,
    String entryId,
  ) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    final page = (await engine.api.get(
      'api/v1/conversations/entries/$entryId/',
      headers: {'X-Makolo-Profile': profileId},
    )).jsonObject();
    if (page['viewer_profile_id'] != profileId ||
        page['point_id'] != pointId ||
        page['target_id'] != entryId ||
        page['scope'] is! String ||
        page['results'] is! List) {
      throw const FormatException('Invalid message context');
    }
    await database.transaction(() async {
      final prior = await exchangeStore.scope(pointId);
      if (prior != null && prior != page['scope']) {
        await exchangeStore.revoke(pointId);
      }
      await exchangeStore.setScope(pointId, page['scope'] as String);
      await exchangeStore.apply(pointId, _entriesForStore(page['results']));
    });
    return page;
  }

  static List<Map<String, dynamic>> _entriesForStore(Object? value) => [
    for (final row in value as List) Map<String, dynamic>.from(row as Map),
  ];
  Future<Map<String, dynamic>> searchExchange(
    String pointId,
    String query, {
    String? cursor,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    final suffix = cursor == null
        ? ''
        : '&cursor=${Uri.encodeQueryComponent(cursor)}';
    final page = (await engine.api.get(
      'api/v1/conversations/points/$pointId/entries/search/?q=${Uri.encodeQueryComponent(query)}$suffix',
      headers: {'X-Makolo-Profile': profileId},
    )).jsonObject();
    if (page['viewer_profile_id'] != profileId ||
        page['point_id'] != pointId ||
        page['scope'] is! String) {
      throw const FormatException('Invalid search scope');
    }
    final priorScope = await exchangeStore.scope(pointId);
    if (priorScope != null && priorScope != page['scope']) {
      await exchangeStore.revoke(pointId);
      page['local_scope_changed'] = true;
    }
    if (page['results'] is! List) {
      throw const FormatException('Invalid owner search');
    }
    return page;
  }

  Future<File> downloadEntryReference({
    required String referenceId,
    required String filename,
    String mode = 'view',
    bool confirm = false,
  }) async {
    if (!RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(referenceId) ||
        !{'view', 'download', 'system_share'}.contains(mode)) {
      throw const FormatException('Invalid reference');
    }
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    final directory = await NativeDirectories.temporary();
    final safeProfile = MakoloDatabase.profileDirectoryKey(profileId);
    final folder = Directory('${directory.path}/conversation-$safeProfile');
    await folder.create(recursive: true);
    final ext = filename.split('.').last;
    final suffix = RegExp(r'^[A-Za-z0-9]{1,9}$').hasMatch(ext) ? ext : 'bin';
    final file = File(
      '${folder.path}/$referenceId-${DateTime.now().microsecondsSinceEpoch}.$suffix',
    );
    try {
      await engine.api.download(
        'api/v1/conversations/references/$referenceId/file/?mode=$mode${confirm ? '&confirm=1' : ''}',
        destinationPath: file.path,
        headers: {'X-Makolo-Profile': profileId},
      );
      return file;
    } on Object {
      if (await file.exists()) await file.delete();
      rethrow;
    }
  }

  Future<Map<String, dynamic>> exchangeReference(String referenceId) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    return (await engine.api.get(
      'api/v1/conversations/references/$referenceId/',
      headers: {'X-Makolo-Profile': profileId},
    )).jsonObject();
  }

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
      if (payload['viewer_profile_id'] != null &&
          payload['viewer_profile_id'] != profileId) {
        throw const FormatException('Conversations Profile changed');
      }
      realtime?.conversations(
        (payload['results'] as List).whereType<Map>().map(
          (row) => row['id'].toString(),
        ),
      );
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

  Stream<StoredProjection?> watchList() async* {
    final socket = realtime;
    socket?.acquireInbox();
    try {
      yield* store.watchProjection(listProjectionKind);
    } finally {
      socket?.releaseInbox();
    }
  }

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

  Future<void>? _listRefresh;
  Future<void> refreshList() =>
      _listRefresh ??= _refreshList().whenComplete(() => _listRefresh = null);
  Future<void> _refreshList() async {
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

  /// Reconcile only the confirmed row, preserving the age of all other data.
  /// An unavailable refresh is not a second or failed owner mutation.
  Future<void> _forgetConfirmedPendingRow(String section, String id) async {
    try {
      final prior = await readInvitations();
      if (prior == null || prior.payload[section] is! List) return;
      final rows = (prior.payload[section] as List)
          .where((row) => row is Map && row['id']?.toString() != id)
          .toList(growable: false);
      await store.putProjection(
        kind: invitationsProjectionKind,
        schemaVersion: prior.schemaVersion,
        payload: {
          ...prior.payload,
          section: rows,
          if (section == 'results') 'count': rows.length,
        },
        receivedAt: prior.receivedAt,
        freshnessPolicyId: invitationsFreshness.id,
        expiresAt: prior.expiresAt,
      );
    } on Object {
      // The confirmed decision still belongs to the server.
    }
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
    int limit = 50,
  }) async {
    final engine = sync;
    if (engine == null) throw StateError('Connexion indisponible.');
    final before = cursor == null
        ? ''
        : '&before_sequence=${Uri.encodeQueryComponent(cursor)}';
    try {
      final response = await engine.api.get(
        'api/v1/conversations/points/$pointId/entries/?order=latest&limit=$limit$before',
        headers: {'X-Makolo-Profile': profileId},
      );
      final page = response.jsonObject();
      if (page['viewer_profile_id'] != profileId || page['results'] is! List) {
        throw const FormatException('Invalid Exchange history scope');
      }
      final rows = (page['results'] as List)
          .map((row) => Map<String, dynamic>.from(row as Map))
          .toList();
      await database.transaction(() async {
        final priorScope = await exchangeStore.scope(pointId);
        final scope = page['scope'];
        if (scope is! String) {
          throw const FormatException('Invalid Exchange history scope');
        }
        if (priorScope != null && priorScope != scope) {
          await exchangeStore.revoke(pointId);
        }
        await exchangeStore.setScope(pointId, scope);
        await exchangeStore.apply(pointId, rows);
      });
      return {...page, 'next_cursor': page['before_sequence']?.toString()};
    } on MakoloApiError catch (error) {
      if ({401, 403, 404}.contains(error.statusCode)) {
        await exchangeStore.revoke(pointId);
      }
      rethrow;
    }
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
    final temp = await NativeDirectories.temporary();
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

  Future<void> updatePointRevisit({
    required String conversationId,
    required String pointId,
    required bool revisit,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion requise pour modifier ce repère personnel.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/points/$pointId/personal-state/',
      body: {'revisit': revisit},
    );
    final owner = response.jsonObject();
    if (owner['point_id']?.toString() != pointId ||
        owner['revisit'] != revisit) {
      throw const FormatException('Repère personnel non confirmé.');
    }
    try {
      await refreshDetail(conversationId, focusPointId: pointId);
    } on Object {
      // The owner's confirmed state must not turn into an apparent failure.
    }
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
    if (result['id']?.toString().isEmpty != false ||
        result['kind'] != kind ||
        !{'pending', 'active'}.contains(result['status'])) {
      throw const FormatException('Invitation non confirmée.');
    }
    try {
      await refreshInvitations();
    } on Object {
      // The owner accepted this invitation command. Retry only the read.
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
    if (engine == null) {
      throw StateError('Connexion requise pour modifier les participants.');
    }
    final route = switch (operation) {
      'remove' => 'participants/$resourceId/remove/',
      'cancel' => 'invitations/$resourceId/cancel/',
      'revoke' => 'collectives/$resourceId/revoke/',
      _ => throw ArgumentError.value(operation, 'operation'),
    };
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/$route',
    );
    final payload = response.jsonObject();
    final expected = switch (operation) {
      'remove' => 'removed',
      'cancel' => 'cancelled',
      'revoke' => 'revoked',
      _ => '',
    };
    if (payload['id']?.toString() != resourceId ||
        payload['status'] != expected) {
      throw const FormatException(
        'Modification de participation non confirmée.',
      );
    }
    if (operation == 'cancel' || operation == 'revoke') {
      await _forgetConfirmedPendingRow('sent_results', resourceId);
      try {
        await refreshInvitations();
      } on Object {
        // Keep the confirmed row removal until the next acquisition.
      }
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
    final payload = response.jsonObject();
    if (payload['id']?.toString() != accessId ||
        payload['status'] != (accept ? 'active' : 'declined')) {
      throw const FormatException('Décision non confirmée.');
    }
    await _forgetConfirmedPendingRow('collective_results', accessId);
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
    final payload = response.jsonObject();
    if (payload['id']?.toString() != requestId ||
        payload['status'] != (approve ? 'approved' : 'rejected')) {
      throw const FormatException('Décision non confirmée.');
    }
    await _forgetConfirmedPendingRow('join_requests_to_decide', requestId);
    try {
      await refreshInvitations();
    } on Object {
      // Keep the owner-confirmed decision until refresh resumes.
    }
    try {
      await refreshDetail(conversationId);
    } on Object {
      // Keep the confirmed decision, allow next owner acquisition.
    }
  }

  Future<void> withdrawJoinRequest(String requestId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion requise pour retirer la demande.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/join-requests/$requestId/withdraw/',
    );
    final payload = response.jsonObject();
    if (payload['id']?.toString() != requestId ||
        payload['status'] != 'cancelled') {
      throw const FormatException('Retrait non confirmé par Conversations.');
    }
    await _forgetConfirmedPendingRow('my_join_requests', requestId);
    try {
      await refreshInvitations();
    } on Object {
      // Retrait confirmé ; le prochain cycle réconciliera le snapshot.
    }
  }

  Future<List<Map<String, dynamic>>> conversationJoinRequests(String id) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Connexion requise pour voir les demandes.');
    }
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
    if (engine == null) {
      throw StateError('Connexion requise pour changer de participation.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/entry/',
      body: {'action': action},
    );
    final payload = response.jsonObject();
    final expected = switch (action) {
      'join' => 'active',
      'request' => 'pending',
      'leave' => 'left',
      _ => throw ArgumentError.value(action, 'action'),
    };
    if (payload['id']?.toString().isEmpty != false ||
        payload['status'] != expected) {
      throw const FormatException('État de participation non confirmé.');
    }
    try {
      await refreshInvitations();
    } on Object {
      // The action was confirmed; its projections can reconcile later.
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
    if (payload['id']?.toString() != invitationId ||
        payload['status'] != (accept ? 'accepted' : 'declined')) {
      throw const FormatException('Décision non confirmée.');
    }
    await _forgetConfirmedPendingRow('results', invitationId);
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
    bool? shareReadReceipts,
  }) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Une connexion est nécessaire pour modifier cet état.');
    }
    final response = await engine.api.post(
      'api/v1/conversations/$conversationId/personal-state/',
      headers: {'X-Makolo-Profile': profileId},
      body: {
        'share_read_receipts': ?shareReadReceipts,
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
              'share_read_receipts': confirmed['share_read_receipts'] != false,
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
