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
