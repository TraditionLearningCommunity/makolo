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
    this.when = '',
    this.period = '',
    this.vertical = '',
    this.price = '',
    this.date = '',
    this.dateFrom = '',
    this.dateTo = '',
    this.latitude,
    this.longitude,
    this.radiusKm,
    this.page = 1,
    this.pageSize = 24,
  });

  final String text;
  final String place;
  final String when;
  final String period;
  final String vertical;
  final String price;
  final String date;
  final String dateFrom;
  final String dateTo;
  final double? latitude;
  final double? longitude;
  final double? radiusKm;
  final int page;
  final int pageSize;

  DiscoveryQuery copyWith({
    String? text,
    String? place,
    String? when,
    String? period,
    String? vertical,
    String? price,
    String? date,
    String? dateFrom,
    String? dateTo,
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
      when: when ?? this.when,
      period: period ?? this.period,
      vertical: vertical ?? this.vertical,
      price: price ?? this.price,
      date: date ?? this.date,
      dateFrom: dateFrom ?? this.dateFrom,
      dateTo: dateTo ?? this.dateTo,
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
      if (when.trim().isNotEmpty) 'when': when.trim(),
      if (period.trim().isNotEmpty) 'period': period.trim(),
      if (vertical.trim().isNotEmpty) 'vertical': vertical.trim(),
      if (price.trim().isNotEmpty) 'price': price.trim(),
      if (date.trim().isNotEmpty) 'date': date.trim(),
      if (dateFrom.trim().isNotEmpty) 'date_from': dateFrom.trim(),
      if (dateTo.trim().isNotEmpty) 'date_to': dateTo.trim(),
      if (latitude != null) 'lat': latitude!.toString(),
      if (longitude != null) 'lon': longitude!.toString(),
      if (radiusKm != null) 'radius_km': radiusKm!.toString(),
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
  }

  bool get hasCriteria =>
      text.trim().isNotEmpty ||
      place.trim().isNotEmpty ||
      when.trim().isNotEmpty ||
      period.trim().isNotEmpty ||
      vertical.trim().isNotEmpty ||
      price.trim().isNotEmpty ||
      date.trim().isNotEmpty ||
      dateFrom.trim().isNotEmpty ||
      dateTo.trim().isNotEmpty ||
      latitude != null ||
      longitude != null;

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
  static const activityPreviewProjectionKind = 'discovery.activity-preview';
  static const occurrencePreviewProjectionKind = 'discovery.occurrence-preview';
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

  Stream<StoredProjection?> watchActivityPreview(String id) =>
      store.watchProjection(activityPreviewProjectionKind, resourceKey: id);

  Future<StoredProjection?> readActivityPreview(String id) =>
      store.readProjection(activityPreviewProjectionKind, resourceKey: id);

  Stream<StoredProjection?> watchOccurrencePreview(String id) =>
      store.watchProjection(occurrencePreviewProjectionKind, resourceKey: id);

  Future<StoredProjection?> readOccurrencePreview(String id) =>
      store.readProjection(occurrencePreviewProjectionKind, resourceKey: id);

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

  Future<void> refreshItems(DiscoveryQuery query) async {
    await _refresh(itemsSource(query));
    await indexItemPreviews(query);
  }

  Future<void> indexItemPreviews(DiscoveryQuery query) async {
    final projection = await readItems(query);
    if (projection == null) return;
    await _indexDiscoveryItemPreviews(projection);
  }

  Future<void> refreshMap(DiscoveryQuery query) => _refresh(mapSource(query));

  Future<void> refreshItem(String family, String id) =>
      _refresh(itemSource(family, id));

  Future<void> refreshActivity(String id) async {
    await _refresh(activitySource(id));
    final projection = await readActivity(id);
    if (projection != null) {
      await _indexActivityOccurrencePreviews(id, projection);
    }
  }

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

  Future<void> _indexDiscoveryItemPreviews(StoredProjection projection) async {
    final rawResults = projection.payload['results'];
    if (rawResults is! List) return;

    for (final raw in rawResults.whereType<Map>()) {
      final item = Map<String, dynamic>.from(raw);
      final identity = _map(item['identity']);
      final resource = _map(identity?['resource']);
      final family = _text(identity?['family']);
      final resourceId = _text(resource?['id']);
      if (family == null || resourceId == null) continue;

      if (_isActivityFamily(family)) {
        await _putPreview(
          kind: activityPreviewProjectionKind,
          resourceKey: resourceId,
          payload: {'item': item},
          source: projection,
        );
      }

      final occurrence = _map(identity?['occurrence']);
      final occurrenceId = _text(occurrence?['id']);
      if (occurrenceId != null) {
        await _putPreview(
          kind: occurrencePreviewProjectionKind,
          resourceKey: occurrenceId,
          payload: {'item': item},
          source: projection,
        );
      }
    }
  }

  Future<void> _indexActivityOccurrencePreviews(
    String activityId,
    StoredProjection projection,
  ) async {
    final representation = _map(projection.payload['representation']);
    final title = _text(representation?['title']);
    final occurrences = projection.payload['occurrences'];
    if (title == null || occurrences is! List) return;

    for (final raw in occurrences.whereType<Map>()) {
      final occurrence = Map<String, dynamic>.from(raw);
      final occurrenceId = _text(occurrence['id']);
      if (occurrenceId == null) continue;
      await _putPreview(
        kind: occurrencePreviewProjectionKind,
        resourceKey: occurrenceId,
        payload: {
          'activity': {'id': activityId, 'title': title},
          'occurrence': occurrence,
          if (projection.payload['availability'] != null)
            'availability': projection.payload['availability'],
        },
        source: projection,
      );
    }
  }

  Future<void> _putPreview({
    required String kind,
    required String resourceKey,
    required Map<String, dynamic> payload,
    required StoredProjection source,
  }) {
    return store.putProjection(
      kind: kind,
      resourceKey: resourceKey,
      schemaVersion: source.schemaVersion,
      payload: payload,
      receivedAt: source.receivedAt,
      sourceGeneratedAt: source.sourceGeneratedAt,
      sourceUpdatedAt: source.sourceUpdatedAt,
      lastVerifiedOnlineAt: source.lastVerifiedOnlineAt,
      freshUntil: source.freshUntil,
      expiresAt: source.expiresAt,
      freshnessPolicyId: source.freshnessPolicyId,
    );
  }

  bool _isActivityFamily(String family) =>
      family == 'activity' ||
      family == 'service_activity' ||
      family == 'funding_activity';

  Map<String, dynamic>? _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : null;

  String? _text(Object? value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? null : text;
  }

  Future<void> _refresh(SyncSourceDefinition source) async {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Discovery owner is not configured.');
    }
    await engine.refreshSource(source);
  }
}
