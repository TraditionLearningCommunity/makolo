import 'dart:convert';

import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/projection_contract.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

class DiscoveryQuery {
  const DiscoveryQuery({
    this.text = '',
    this.place = '',
    this.latitude,
    this.longitude,
    this.radiusKm,
    this.page = 1,
    this.pageSize = 24,
  });

  final String text;
  final String place;
  final double? latitude;
  final double? longitude;
  final double? radiusKm;
  final int page;
  final int pageSize;

  DiscoveryQuery copyWith({
    String? text,
    String? place,
    double? latitude,
    double? longitude,
    double? radiusKm,
    int? page,
    int? pageSize,
    bool clearLocation = false,
  }) {
    return DiscoveryQuery(
      text: text ?? this.text,
      place: place ?? this.place,
      latitude: clearLocation ? null : latitude ?? this.latitude,
      longitude: clearLocation ? null : longitude ?? this.longitude,
      radiusKm: clearLocation ? null : radiusKm ?? this.radiusKm,
      page: page ?? this.page,
      pageSize: pageSize ?? this.pageSize,
    );
  }

  Map<String, String> get parameters {
    return <String, String>{
      if (text.trim().isNotEmpty) 'q': text.trim(),
      if (place.trim().isNotEmpty) 'place': place.trim(),
      if (latitude != null) 'lat': latitude!.toString(),
      if (longitude != null) 'lon': longitude!.toString(),
      if (radiusKm != null) 'radius_km': radiusKm!.toString(),
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
  }

  String get canonicalQuery {
    final entries = parameters.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return Uri(queryParameters: Map.fromEntries(entries)).query;
  }

  String get fingerprint =>
      base64Url.encode(utf8.encode(canonicalQuery)).replaceAll('=', '');

  String get path => canonicalQuery.isEmpty
      ? 'api/v1/discovery/items/'
      : 'api/v1/discovery/items/?$canonicalQuery';

  String get mapCanonicalQuery {
    final entries = Map<String, String>.from(parameters)
      ..remove('page')
      ..remove('page_size');
    final sorted = entries.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return Uri(queryParameters: Map.fromEntries(sorted)).query;
  }

  String get mapFingerprint =>
      base64Url.encode(utf8.encode(mapCanonicalQuery)).replaceAll('=', '');

  String get mapPath {
    final query = mapCanonicalQuery;
    return query.isEmpty
        ? 'api/v1/discovery/map/'
        : 'api/v1/discovery/map/?$query';
  }
}

class DiscoverySourceState {
  const DiscoverySourceState({
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

  static const unknown = DiscoverySourceState();
}

class DiscoveryRepository {
  DiscoveryRepository({
    required this.database,
    required this.store,
    required this.profileId,
    required this.api,
    this.sync,
  });

  static const itemsProjectionKind = 'discovery.items';
  static const itemProjectionKind = 'discovery.item';
  static const mapProjectionKind = 'discovery.map';
  static const activityProjectionKind = 'activity.detail';
  static const occurrenceProjectionKind = 'occurrence.detail';
  static const watchesProjectionKind = 'discovery.watches';
  static const watchResultsProjectionKind = 'discovery.watch-results';

  static const discoveryFreshness = FreshnessPolicy(
    id: 'discovery-pack',
    refreshRecommendedAfter: Duration(minutes: 15),
    usableButOldAfter: Duration(hours: 6),
  );

  static const detailFreshness = FreshnessPolicy(
    id: 'discovery-detail',
    refreshRecommendedAfter: Duration(minutes: 30),
    usableButOldAfter: Duration(hours: 12),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final MakoloApiClient api;
  final SyncEngine? sync;

  SyncSourceDefinition itemsSource(DiscoveryQuery query) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'discovery:${query.fingerprint}',
      owner: 'Discovery',
      path: query.path,
      projectionKind: itemsProjectionKind,
      resourceKey: query.fingerprint,
      category: SyncSourceCategory.collection,
      freshnessPolicy: discoveryFreshness,
    );
  }

  SyncSourceDefinition mapSource(DiscoveryQuery query) {
    return SyncSourceDefinition(
      sourceKey: 'discovery-map:${query.mapFingerprint}',
      owner: 'Discovery',
      path: query.mapPath,
      projectionKind: mapProjectionKind,
      resourceKey: query.mapFingerprint,
      category: SyncSourceCategory.collection,
      freshnessPolicy: discoveryFreshness,
      parser: (response) {
        final payload = response.jsonObject();
        return AcquiredProjection(schemaVersion: 1, payload: payload);
      },
      applier: applyProjectionSnapshot,
    );
  }

  SyncSourceDefinition itemSource(String family, String id) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'discovery-item:$family:$id',
      owner: 'Discovery',
      path: 'api/v1/discovery/items/$family/$id/',
      projectionKind: itemProjectionKind,
      resourceKey: '$family:$id',
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: detailFreshness,
    );
  }

  SyncSourceDefinition activitySource(String id) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'activity:$id',
      owner: 'Activities',
      path: 'api/v1/activities/$id/',
      projectionKind: activityProjectionKind,
      resourceKey: id,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: detailFreshness,
    );
  }

  SyncSourceDefinition occurrenceSource(String id) {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'occurrence:$id',
      owner: 'Occurrences',
      path: 'api/v1/occurrences/$id/',
      projectionKind: occurrenceProjectionKind,
      resourceKey: id,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: detailFreshness,
    );
  }

  SyncSourceDefinition watchResultsSource(String watchId, {int page = 1}) {
    final resourceKey = '$watchId:$page';
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'discovery-watch-results:$resourceKey',
      owner: 'Discovery',
      path:
          'api/v1/discovery/watches/$watchId/results/?page=$page&page_size=24',
      projectionKind: watchResultsProjectionKind,
      resourceKey: resourceKey,
      category: SyncSourceCategory.collection,
      freshnessPolicy: discoveryFreshness,
    );
  }

  SyncSourceDefinition watchesSource() {
    return SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'discovery-watches',
      owner: 'Discovery',
      path: 'api/v1/discovery/watches/',
      projectionKind: watchesProjectionKind,
      category: SyncSourceCategory.collection,
      freshnessPolicy: detailFreshness,
    );
  }

  Stream<StoredProjection?> watchItems(DiscoveryQuery query) => store
      .watchProjection(itemsProjectionKind, resourceKey: query.fingerprint);

  Future<StoredProjection?> readItems(DiscoveryQuery query) =>
      store.readProjection(itemsProjectionKind, resourceKey: query.fingerprint);

  Stream<StoredProjection?> watchMap(DiscoveryQuery query) => store
      .watchProjection(mapProjectionKind, resourceKey: query.mapFingerprint);

  Future<StoredProjection?> readMap(DiscoveryQuery query) => store
      .readProjection(mapProjectionKind, resourceKey: query.mapFingerprint);

  Stream<StoredProjection?> watchItem(String family, String id) =>
      store.watchProjection(itemProjectionKind, resourceKey: '$family:$id');

  Future<StoredProjection?> readItem(String family, String id) =>
      store.readProjection(itemProjectionKind, resourceKey: '$family:$id');

  Stream<StoredProjection?> watchActivity(String id) =>
      store.watchProjection(activityProjectionKind, resourceKey: id);

  Future<StoredProjection?> readActivity(String id) =>
      store.readProjection(activityProjectionKind, resourceKey: id);

  Stream<StoredProjection?> watchOccurrence(String id) =>
      store.watchProjection(occurrenceProjectionKind, resourceKey: id);

  Future<StoredProjection?> readOccurrence(String id) =>
      store.readProjection(occurrenceProjectionKind, resourceKey: id);

  Stream<StoredProjection?> watchWatches() =>
      store.watchProjection(watchesProjectionKind);

  Stream<StoredProjection?> watchWatchResults(String watchId, {int page = 1}) =>
      store.watchProjection(
        watchResultsProjectionKind,
        resourceKey: '$watchId:$page',
      );

  Future<StoredProjection?> readWatchResults(String watchId, {int page = 1}) =>
      store.readProjection(
        watchResultsProjectionKind,
        resourceKey: '$watchId:$page',
      );

  Future<DiscoverySourceState> readSource(SyncSourceDefinition source) async {
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(source.sourceKey),
      );
    final row = await query.getSingleOrNull();
    return row == null
        ? DiscoverySourceState.unknown
        : DiscoverySourceState(
            lastSuccessAt: row.lastSuccessAt,
            invalidated: row.invalidated,
            lastErrorCode: row.lastErrorCode,
          );
  }

  Stream<DiscoverySourceState> watchSource(SyncSourceDefinition source) {
    final query = database.select(database.syncSources)
      ..where(
        (row) =>
            row.profileId.equals(profileId) &
            row.sourceKey.equals(source.sourceKey),
      );
    return query.watchSingleOrNull().map(
      (row) => row == null
          ? DiscoverySourceState.unknown
          : DiscoverySourceState(
              lastSuccessAt: row.lastSuccessAt,
              invalidated: row.invalidated,
              lastErrorCode: row.lastErrorCode,
            ),
    );
  }

  Future<void> refreshItems(DiscoveryQuery query) =>
      _refresh(itemsSource(query));

  Future<void> refreshMap(DiscoveryQuery query) => _refresh(mapSource(query));

  Future<void> refreshItem(String family, String id) =>
      _refresh(itemSource(family, id));

  Future<void> refreshActivity(String id) => _refresh(activitySource(id));

  Future<void> refreshOccurrence(String id) => _refresh(occurrenceSource(id));

  Future<void> refreshWatches() => _refresh(watchesSource());

  Future<void> refreshWatchResults(String watchId, {int page = 1}) =>
      _refresh(watchResultsSource(watchId, page: page));

  Future<void> setSaved({
    required String family,
    required String id,
    required bool saved,
  }) async {
    final path = 'api/v1/discovery/items/$family/$id/saved/';
    final response = saved ? await api.put(path) : await api.delete(path);
    final envelope = ProjectionEnvelope.parse(response.jsonObject());
    if (envelope.projection != 'discovery.saved') {
      throw FormatException(
        'Expected discovery.saved, got ${envelope.projection}',
      );
    }
    final item = envelope.data['item'];
    if (item is! Map) {
      throw const FormatException('Missing saved Discovery item.');
    }
    await store.putProjection(
      kind: itemProjectionKind,
      resourceKey: '$family:$id',
      schemaVersion: envelope.schemaVersion,
      payload: {'item': Map<String, dynamic>.from(item)},
      sourceGeneratedAt: envelope.generatedAt,
      freshnessPolicyId: detailFreshness.id,
    );
  }

  Future<void> _refresh(SyncSourceDefinition source) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Discovery owner is not configured.');
    }
    await engine.refreshSource(source);
  }
}
