import '../data/local/profile_store.dart';
import '../network/makolo_api_client.dart';
import '../sync/projection_contract.dart';
import '../sync/owner_source_state.dart';

class PersonalRepository {
  PersonalRepository(this.store);

  final ProfileStore store;

  Stream<StoredProjection?> watchNow() => store.watchProjection('personal.now');

  Stream<OwnerSourceState> watchNowSource() => watchOwnerSourceState(
    database: store.database,
    profileId: store.profileId,
    sourceKey: 'personal.now',
  );

  Stream<StoredProjection?> watchOngoing() =>
      store.watchProjection('personal.ongoing');

  Stream<OwnerSourceState> watchOngoingSource() => watchOwnerSourceState(
    database: store.database,
    profileId: store.profileId,
    sourceKey: 'personal.ongoing',
  );

  Stream<StoredProjection?> watchMe() => store.watchProjection('personal.me');

  Stream<OwnerSourceState> watchMeSource() => watchOwnerSourceState(
    database: store.database,
    profileId: store.profileId,
    sourceKey: 'personal.me',
  );

  /// Append one bounded N1 territory continuation to the existing local
  /// personal.me snapshot. The server remains the only source of facts.
  Future<void> loadMoreMe({
    required MakoloApiClient api,
    required StoredProjection current,
    required String territory,
  }) async {
    const keys = <String, List<String>>{
      'considerations': [
        'interests', 'open_to', 'watches', 'bookmarks',
        'followed_spaces', 'followed_profiles',
      ],
      'collectives': ['authorized_spaces', 'teams', 'groups'],
      'resources': ['documents', 'proofs', 'credentials'],
    };
    final collections = current.payload[territory];
    final names = keys[territory];
    if (names == null || collections is! Map) return;
    final owned = Map<String, dynamic>.from(collections);
    final more = names.where((key) {
      final collection = owned[key];
      return collection is Map && collection['has_more'] == true;
    }).toList();
    if (more.isEmpty) return;
    final offsets = more.map((key) {
      final items = (owned[key] as Map)['items'];
      return items is List ? items.length : 0;
    }).toList();
    // Each family has its own offset; query individual families at their
    // exact next index so uneven datasets cannot duplicate or skip rows.
    for (var i = 0; i < more.length; i++) {
      final key = more[i];
      final offset = offsets[i];
      final uri = Uri(
        path: 'api/v1/me/preview/$territory/',
        queryParameters: {'offset': '$offset', 'limit': '24'},
      );
      final response = await api.get(uri.toString());
      final envelope = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.preview',
      );
      final data = envelope.data;
      if (data['territory'] != territory || data['offset'] != offset) {
        throw const FormatException('Invalid personal.me continuation');
      }
      final page = data['collections'];
      if (page is! Map) throw const FormatException('Invalid Me page');
      // This endpoint pages each family with the given offset. Only merge
      // the requested family; the rest are returned but not applied here.
      final part = page[key];
      if (part is! Map || part['items'] is! List) {
        throw const FormatException('Invalid Me family');
      }
      final previous = owned[key] as Map;
      final priorItems = previous['items'];
      if (priorItems is! List) throw const FormatException('Invalid Me cache');
      final combined = <Object>[];
      final ids = <String>{};
      for (final row in [...priorItems, ...(part['items'] as List)]) {
        if (row is! Map || row['id'] == null) {
          throw const FormatException('Invalid Me row identity');
        }
        final id = row['id'].toString();
        if (ids.add(id)) combined.add(Map<String, dynamic>.from(row));
      }
      owned[key] = <String, dynamic>{
        'items': combined,
        'count': part['count'],
        'has_more': part['has_more'],
      };
    }
    final merged = Map<String, dynamic>.from(current.payload)
      ..[territory] = owned;
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: current.schemaVersion,
      payload: merged,
      receivedAt: DateTime.now().toUtc(),
      sourceGeneratedAt: current.sourceGeneratedAt,
      freshUntil: current.freshUntil,
      freshnessPolicyId: current.freshnessPolicyId,
    );
  }

  /// Reconcile a Discovery-confirmed save in the cached ongoing display only.
  /// The bookmark is owned by Discovery; this does not create a new saved fact.
  Future<void> reflectOngoingDiscoverySave({
    required String activityId,
    required bool saved,
  }) async {
    final snapshot = await store.readProjection('personal.ongoing');
    if (snapshot == null) return;
    final raw = snapshot.payload['items'];
    if (raw is! List) return;
    var changed = false;
    final items = <Object>[];
    for (final entry in raw) {
      if (entry is! Map) {
        items.add(entry);
        continue;
      }
      final item = Map<String, dynamic>.from(entry);
      final n1 = item['n1'];
      if (n1 is Map && n1['possibility'] is Map &&
          (n1['possibility'] as Map)['id'] == activityId) {
        final possibility = Map<String, dynamic>.from(n1['possibility'] as Map)
          ..['saved_state'] = saved ? 'saved' : 'not_saved'
          ..['capabilities'] = [saved ? 'unsave' : 'save', 'share'];
        item['n1'] = Map<String, dynamic>.from(n1)
          ..['possibility'] = possibility;
        changed = true;
      }
      items.add(item);
    }
    if (!changed) return;
    await store.putProjection(
      kind: 'personal.ongoing',
      schemaVersion: snapshot.schemaVersion,
      payload: Map<String, dynamic>.from(snapshot.payload)..['items'] = items,
      receivedAt: snapshot.receivedAt,
      sourceGeneratedAt: snapshot.sourceGeneratedAt,
      sourceUpdatedAt: snapshot.sourceUpdatedAt,
      lastVerifiedOnlineAt: snapshot.lastVerifiedOnlineAt,
      freshUntil: snapshot.freshUntil,
      expiresAt: snapshot.expiresAt,
      freshnessPolicyId: snapshot.freshnessPolicyId,
    );
  }

  /// Continue the server-owned personal field without losing the cached prefix.
  /// Only one profile-scoped snapshot is persisted; this is not a second truth.
  Future<void> loadMoreOngoing({
    required MakoloApiClient api,
    required StoredProjection current,
  }) async {
    final continuation = current.payload['continuation'];
    final token = continuation is Map ? continuation['token'] : null;
    if (token is! String || token.trim().isEmpty) return;
    final path = Uri(
      path: 'api/v1/me/ongoing/',
      queryParameters: {'continuation': token},
    ).toString();
    final response = await api.get(path);
    final envelope = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'personal.ongoing',
    );
    final data = envelope.data;
    final actor = data['actor'];
    if (data['surface'] != 'ongoing_me' ||
        actor is! Map ||
        actor['type'] != 'profile' ||
        actor['id']?.toString() != store.profileId) {
      throw const FormatException('Invalid OngoingMe actor context');
    }
    final nextRows = data['items'];
    final knownRows = current.payload['items'];
    if (nextRows is! List || knownRows is! List) {
      throw const FormatException('Invalid OngoingMe continuation');
    }
    final items = <Object>[];
    final seen = <String, int>{};
    for (final row in [...knownRows, ...nextRows]) {
      if (row is! Map) {
        throw const FormatException('Invalid OngoingMe row');
      }
      final key = row['id']?.toString();
      if (key == null || key.isEmpty) {
        throw const FormatException('Missing OngoingMe identity');
      }
      final previous = seen[key];
      if (previous == null) {
        seen[key] = items.length;
        items.add(Map<String, dynamic>.from(row));
      } else {
        items[previous] = Map<String, dynamic>.from(row);
      }
    }
    final merged = Map<String, dynamic>.from(current.payload)
      ..['items'] = items
      ..['continuation'] = data['continuation']
      ..['coverage_state'] = data['coverage_state'];
    await store.putProjection(
      kind: 'personal.ongoing',
      schemaVersion: current.schemaVersion,
      payload: merged,
      receivedAt: DateTime.now().toUtc(),
      sourceGeneratedAt: envelope.generatedAt,
      freshUntil: current.freshUntil,
      freshnessPolicyId: current.freshnessPolicyId,
    );
  }

}
