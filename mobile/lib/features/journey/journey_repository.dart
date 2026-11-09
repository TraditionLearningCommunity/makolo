import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class JourneySourceState {
  const JourneySourceState({
    this.lastSuccessAt,
    this.invalidated = false,
    this.lastErrorCode,
  });

  final DateTime? lastSuccessAt;
  final bool invalidated;
  final String? lastErrorCode;

  ReachabilityState get reachability => reachabilityFromSource(
    lastSuccessAt: lastSuccessAt,
    lastErrorCode: lastErrorCode,
  );

  static const unknown = JourneySourceState();
}

class JourneyRepository {
  JourneyRepository({
    required this.database,
    required this.store,
    required this.profileId,
    this.sync,
  });

  static const projectionKind = 'personal.journey.detail';

  static const freshnessPolicy = FreshnessPolicy(
    id: 'journey-contextual',
    refreshRecommendedAfter: Duration(hours: 1),
    usableButOldAfter: Duration(hours: 24),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncEngine? sync;

  SyncSourceDefinition sourceFor(String journeyId) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'journey:$journeyId',
      owner: 'Journeys',
      path: 'api/v1/me/journeys/$journeyId/',
      projectionKind: projectionKind,
      resourceKey: journeyId,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: freshnessPolicy,
    );
  }

  /// Owner identity comes only from a durable personal projection, never a
  /// caller-provided list or a client-generated Journey.
  static List<String> knownJourneyIdsFromOngoing(
    StoredProjection? ongoing, {
    int limit = 6,
  }) {
    if (limit <= 0) return const [];
    final items = ongoing?.payload['items'];
    if (items is! List) return const [];

    final ids = <String>{};
    final uuid = RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    );
    for (final row in items) {
      if (row is! Map) continue;
      final source = row['source'];
      if (source is! Map || source['kind'] != 'journey') continue;
      final raw = source['id'];
      if (raw is! String || !uuid.hasMatch(raw)) continue;
      if (!ids.add(raw)) continue;
      if (ids.length >= limit) break;
    }
    return List.unmodifiable(ids);
  }

  static bool _isUuid(String value) {
    final parts = value.split('-');
    const sizes = [8, 4, 4, 4, 12];
    if (parts.length != sizes.length) return false;
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].length != sizes[i] ||
          int.tryParse(parts[i], radix: 16) == null)
        return false;
    }
    return true;
  }

  /// Only owner links already acquired in the Profile database are prepared.
  static Map<String, String> knownFormLinksFromDetail(
    StoredProjection? detail, {
    int limit = 6,
  }) {
    if (detail == null || limit <= 0) return const {};
    final rows = detail.payload['forms'];
    if (rows is! List) return const {};
    final links = <String, String>{};
    for (final row in rows) {
      if (row is! Map) continue;
      final id = row['id']?.toString() ?? '';
      final ownerLinks = row['links'];
      if (ownerLinks is! Map) continue;
      final link = ownerLinks['detail']?.toString() ?? '';
      if (!_isUuid(id) || link != '/api/v1/questionnaires/requests/$id/') {
        continue;
      }
      links[id] = link;
      if (links.length >= limit) break;
    }
    return Map.unmodifiable(links);
  }

  static Map<String, String> knownRequirementLinksFromDetail(
    StoredProjection? detail, {
    required String journeyId,
    int limit = 6,
  }) {
    if (detail == null || limit <= 0) return const {};
    final rows = detail.payload['requirements'];
    if (rows is! List) return const {};
    final links = <String, String>{};
    for (final row in rows) {
      if (row is! Map) continue;
      final id = row['id']?.toString() ?? '';
      final link = row['link']?.toString() ?? '';
      if (!_isUuid(id) ||
          !_isUuid(journeyId) ||
          link != '/api/v1/me/journeys/$journeyId/requirements/$id/') {
        continue;
      }
      links[id] = link;
      if (links.length >= limit) break;
    }
    return Map.unmodifiable(links);
  }

  /// Prepare owner details already referenced by the personal working set.
  /// Only stored Profile facts select identities; no page or widget cache.
  Future<int> prepareKnownJourneySources({int limit = 6}) async {
    final engine = sync;
    if (engine == null || limit <= 0) return 0;
    final ongoing = await store.readProjection('personal.ongoing');
    final ids = knownJourneyIdsFromOngoing(ongoing, limit: limit);
    for (final id in ids) {
      engine.registerPreparedSource(sourceFor(id));
    }
    return ids.length;
  }

  Stream<StoredProjection?> watchDetail(String journeyId) {
    return store.watchProjection(projectionKind, resourceKey: journeyId);
  }

  Future<StoredProjection?> readDetail(String journeyId) {
    return store.readProjection(projectionKind, resourceKey: journeyId);
  }

  Stream<JourneySourceState> watchSource(String journeyId) {
    final sourceKey = sourceFor(journeyId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? JourneySourceState.unknown
          : JourneySourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<JourneySourceState> readSource(String journeyId) async {
    final sourceKey = sourceFor(journeyId).sourceKey;
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) & row.sourceKey.equals(sourceKey),
      );
    final row = await query.getSingleOrNull();
    return row == null
        ? JourneySourceState.unknown
        : JourneySourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  Future<void> refreshDetail(String journeyId) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Journey owner is not configured.');
    }
    await engine.refreshSource(sourceFor(journeyId));
  }

  Future<void> invalidateDetail(String journeyId) async {
    final engine = sync;
    if (engine == null) return;
    await engine.invalidate(sourceFor(journeyId));
  }
}
