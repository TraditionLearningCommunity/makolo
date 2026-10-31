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

  /// Continue exactly one owner family and merge it into the profile-local
  /// projection. No parallel array offsets and no second persistent truth.
  Future<void> loadMoreMe({
    required MakoloApiClient api,
    required StoredProjection current,
    required String territory,
  }) async {
    const families = <String, List<String>>{
      'considerations': [
        'interests',
        'open_to',
        'watches',
        'bookmarks',
        'followed_spaces',
        'followed_profiles',
      ],
      'collectives': ['authorized_spaces', 'teams', 'groups'],
      'resources': ['documents', 'proofs', 'credentials'],
    };
    final names = families[territory];
    final initial = current.payload[territory];
    if (names == null || initial is! Map) return;
    final target = names.where(
      (key) => initial[key] is Map && (initial[key] as Map)['has_more'] == true,
    );
    if (target.isEmpty) return;
    final family = target.first;
    final source = initial[family] as Map;
    final rows = source['items'];
    if (rows is! List) throw const FormatException('Invalid Me collection');
    final serverOffset = source['next_offset'];
    final offset = serverOffset is int && serverOffset >= rows.length
        ? serverOffset
        : rows.length;

    final response = await api.get(
      Uri(
        path: 'api/v1/me/preview/$territory/',
        queryParameters: {'family': family, 'offset': '$offset', 'limit': '24'},
      ).toString(),
    );
    final envelope = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'personal.me.preview',
    );
    final data = envelope.data;
    final actor = data['actor'];
    final next = data['collection'];
    if (actor is! Map ||
        actor['type'] != 'profile' ||
        actor['id']?.toString() != store.profileId ||
        data['territory'] != territory ||
        data['family'] != family ||
        data['offset'] != offset ||
        next is! Map ||
        next['items'] is! List ||
        next['count'] is! int ||
        next['has_more'] is! bool ||
        next['next_offset'] is! int ||
        next['next_offset'] < offset) {
      throw const FormatException('Invalid Me continuation');
    }

    // Never write a continuation over a newly synchronized root or another
    // profile-local update that changed this family in the meantime.
    final latest = await store.readProjection('personal.me');
    if (latest == null ||
        latest.sourceGeneratedAt != current.sourceGeneratedAt ||
        latest.schemaVersion != current.schemaVersion) {
      return;
    }
    final latestTerritory = latest.payload[territory];
    if (latestTerritory is! Map || latestTerritory[family] is! Map) return;
    final latestItems = (latestTerritory[family] as Map)['items'];
    final latestSource = latestTerritory[family] as Map;
    if (latestItems is! List ||
        (latestSource['next_offset'] is int
            ? latestSource['next_offset'] != offset
            : latestItems.length != offset)) {
      return;
    }

    final seen = <String>{};
    final combined = <Map<String, dynamic>>[];
    for (final row in [...latestItems, ...(next['items'] as List)]) {
      if (row is! Map || row['id'] == null) {
        throw const FormatException('Invalid Me row');
      }
      final id = row['id'].toString();
      if (seen.add(id)) combined.add(Map<String, dynamic>.from(row));
    }
    if (next['has_more'] == true && (next['items'] as List).isEmpty) {
      throw const FormatException('Me continuation did not advance');
    }
    final revised = Map<String, dynamic>.from(latestTerritory)
      ..[family] = {
        'items': combined,
        'count': next['count'],
        'has_more': next['has_more'],
        'next_offset': next['next_offset'],
      };
    final updated = Map<String, dynamic>.from(latest.payload)
      ..[territory] = revised;
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: latest.schemaVersion,
      payload: updated,
      receivedAt: latest.receivedAt,
      sourceGeneratedAt: latest.sourceGeneratedAt,
      sourceUpdatedAt: latest.sourceUpdatedAt,
      lastVerifiedOnlineAt: latest.lastVerifiedOnlineAt,
      freshUntil: latest.freshUntil,
      expiresAt: latest.expiresAt,
      freshnessPolicyId: latest.freshnessPolicyId,
    );
  }

  /// Retain only server-confirmed explicit choices inside the existing
  /// personal.me read model. No local inference, queued mutation, or second
  /// source of truth. A newer root synchronization takes precedence.
  Future<void> reflectMeConfirmedChoices({
    required Map<String, dynamic> settings,
    DateTime? confirmedAt,
  }) async {
    final topicRows = settings['selected_topics'];
    final interestIds = settings['interests'];
    final openIds = settings['open_to'];
    final openOptions = settings['open_to_options'];
    if (topicRows is! List ||
        interestIds is! List ||
        openIds is! List ||
        openOptions is! List) {
      return;
    }
    final interests = interestIds.map((id) => id.toString()).toSet();
    final openness = openIds.map((id) => id.toString()).toSet();
    final topics = <Map<String, dynamic>>[];
    final opens = <Map<String, dynamic>>[];
    for (final raw in topicRows) {
      if (raw is! Map ||
          raw['id'] == null ||
          raw['label'] is! String ||
          !interests.contains(raw['id'].toString())) {
        return;
      }
      topics.add({'id': raw['id'].toString(), 'label': raw['label']});
    }
    for (final raw in openOptions) {
      if (raw is! Map || raw['id'] == null || raw['label'] is! String) {
        return;
      }
      if (openness.contains(raw['id'].toString())) {
        opens.add({'id': raw['id'].toString(), 'label': raw['label']});
      }
    }
    if (topics.length != interests.length || opens.length != openness.length) {
      return;
    }
    final current = await store.readProjection('personal.me');
    if (current == null) return;
    final actor = current.payload['actor'];
    final section = current.payload['considerations'];
    if (actor is! Map ||
        actor['type'] != 'profile' ||
        actor['id']?.toString() != store.profileId ||
        section is! Map) {
      return;
    }
    if (confirmedAt != null &&
        current.sourceGeneratedAt != null &&
        current.sourceGeneratedAt!.isAfter(confirmedAt)) {
      return;
    }
    final latest = await store.readProjection('personal.me');
    if (latest == null ||
        latest.receivedAt != current.receivedAt ||
        latest.sourceGeneratedAt != current.sourceGeneratedAt) {
      return;
    }
    Map<String, dynamic> revised(
      String family,
      List<Map<String, dynamic>> rows,
    ) {
      final old = section[family];
      return {
        if (old is Map) ...old.map((k, v) => MapEntry(k.toString(), v)),
        'items': rows,
        'count': rows.length,
        'next_offset': rows.length,
        'has_more': false,
      };
    }

    final updated = Map<String, dynamic>.from(section)
      ..['interests'] = revised('interests', topics)
      ..['open_to'] = revised('open_to', opens);
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: current.schemaVersion,
      payload: {...current.payload, 'considerations': updated},
      receivedAt: current.receivedAt,
      sourceGeneratedAt: current.sourceGeneratedAt,
      sourceUpdatedAt: current.sourceUpdatedAt,
      lastVerifiedOnlineAt: current.lastVerifiedOnlineAt,
      freshUntil: current.freshUntil,
      expiresAt: current.expiresAt,
      freshnessPolicyId: current.freshnessPolicyId,
    );
  }

  /// Reflect a server-confirmed bookmark removal in the existing Me
  /// projection. The collection remains owned by Discovery; this is only a
  /// profile-local read-model update for offline continuity.
  Future<void> reflectMeBookmarkRemoved({required String activityId}) async {
    final current = await store.readProjection('personal.me');
    if (current == null) return;
    final actor = current.payload['actor'];
    if (actor is! Map ||
        actor['type'] != 'profile' ||
        actor['id']?.toString() != store.profileId) {
      return;
    }
    final considerations = current.payload['considerations'];
    if (considerations is! Map) return;
    final bookmarks = considerations['bookmarks'];
    if (bookmarks is! Map || bookmarks['items'] is! List) return;
    final original = bookmarks['items'] as List;
    final retained = original.where((raw) {
      if (raw is! Map || raw['activity'] is! Map) return true;
      return (raw['activity'] as Map)['id']?.toString() != activityId;
    }).toList();
    if (retained.length == original.length) return;

    // Avoid restoring a stale collection over a newer root sync.
    final latest = await store.readProjection('personal.me');
    if (latest == null ||
        latest.receivedAt != current.receivedAt ||
        latest.sourceGeneratedAt != current.sourceGeneratedAt) {
      return;
    }
    final revisedCollection = Map<String, dynamic>.from(bookmarks);
    revisedCollection['items'] = retained;
    if (revisedCollection['count'] is int &&
        (revisedCollection['count'] as int) > 0) {
      revisedCollection['count'] = (revisedCollection['count'] as int) - 1;
    }
    if (revisedCollection['next_offset'] is int &&
        (revisedCollection['next_offset'] as int) > 0) {
      revisedCollection['next_offset'] =
          (revisedCollection['next_offset'] as int) - 1;
    }
    final revisedConsiderations = Map<String, dynamic>.from(considerations)
      ..['bookmarks'] = revisedCollection;
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: current.schemaVersion,
      payload: {...current.payload, 'considerations': revisedConsiderations},
      receivedAt: current.receivedAt,
      sourceGeneratedAt: current.sourceGeneratedAt,
      sourceUpdatedAt: current.sourceUpdatedAt,
      lastVerifiedOnlineAt: current.lastVerifiedOnlineAt,
      freshUntil: current.freshUntil,
      expiresAt: current.expiresAt,
      freshnessPolicyId: current.freshnessPolicyId,
    );
  }

  /// Reflect a confirmed Discovery save in the already-cached Ongoing N1
  /// projection. Discovery owns the mutation; this only updates its local
  /// presentation, without creating another persistent bookmark.
  Future<void> reflectOngoingDiscoverySave({
    required String activityId,
    required bool saved,
  }) async {
    final current = await store.readProjection('personal.ongoing');
    if (current == null) return;
    final rows = current.payload['items'];
    if (rows is! List) return;

    var changed = false;
    final updatedRows = <Object>[];
    for (final raw in rows) {
      if (raw is! Map) {
        updatedRows.add(raw);
        continue;
      }
      final row = Map<String, dynamic>.from(raw);
      final n1Raw = row['n1'];
      final n1 = n1Raw is Map ? Map<String, dynamic>.from(n1Raw) : null;
      final possibilityRaw = n1?['possibility'];
      final possibility = possibilityRaw is Map
          ? Map<String, dynamic>.from(possibilityRaw)
          : null;
      if (possibility != null &&
          possibility['id'] == activityId &&
          const {
            'activity',
            'service_activity',
            'funding_activity',
          }.contains(possibility['family']) &&
          possibility['saved_state'] != (saved ? 'saved' : 'not_saved')) {
        n1!['possibility'] = {
          ...possibility,
          'saved_state': saved ? 'saved' : 'not_saved',
        };
        row['n1'] = n1;
        changed = true;
      }
      updatedRows.add(row);
    }
    if (!changed) return;

    // An intervening root refresh wins over this UI-only reflection.
    final latest = await store.readProjection('personal.ongoing');
    if (latest == null ||
        latest.receivedAt != current.receivedAt ||
        latest.sourceGeneratedAt != current.sourceGeneratedAt) {
      return;
    }
    await store.putProjection(
      kind: 'personal.ongoing',
      schemaVersion: latest.schemaVersion,
      payload: {...latest.payload, 'items': updatedRows},
      receivedAt: latest.receivedAt,
      sourceGeneratedAt: latest.sourceGeneratedAt,
      sourceUpdatedAt: latest.sourceUpdatedAt,
      lastVerifiedOnlineAt: latest.lastVerifiedOnlineAt,
      freshUntil: latest.freshUntil,
      expiresAt: latest.expiresAt,
      freshnessPolicyId: latest.freshnessPolicyId,
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
    // Reject an older continuation if a root refresh or another page has
    // already advanced the owner projection during this network request.
    final latest = await store.readProjection('personal.ongoing');
    if (latest == null ||
        latest.schemaVersion != current.schemaVersion ||
        latest.receivedAt != current.receivedAt ||
        latest.sourceGeneratedAt != current.sourceGeneratedAt) {
      return;
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
