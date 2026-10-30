import 'dart:convert';

import 'package:drift/drift.dart';

import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/location/discovery_location_context.dart';
import '../../sync/freshness.dart';
import '../../sync/projection_contract.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';
import 'discovery_selector.dart';
import 'discovery_wire.dart';

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
    this.continuation,
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

  /// Opaque, signed server continuation; never decoded locally.
  final String? continuation;

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
    String? continuation,
    bool clearContinuation = false,
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
      continuation: clearContinuation ? null : continuation,
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
      ...DiscoveryLocationContext.parameters,
      'page': page.toString(),
      'page_size': pageSize.toString(),
      'continuation': ?continuation,
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
      ..remove('page_size')
      ..remove('continuation');
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

  /// A 403/404 owner reply invalidates the keyed detail and its N1 preview.
  /// Transport failures alone must not discard an offline snapshot.
  bool get ownerUnavailable =>
      invalidated &&
      const {
        'permission_denied',
        'not_found',
        'api_error',
        'http_403',
        'http_404',
      }.contains(lastErrorCode);

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
  static const presentedWindowKind = 'discovery.presented-window';
  static const int maxPresentedWindowItems = 50;
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
    return SyncSourceDefinition(
      sourceKey: 'discovery:${query.fingerprint}',
      owner: 'Discovery',
      path: query.path,
      projectionKind: itemsProjectionKind,
      resourceKey: query.fingerprint,
      category: SyncSourceCategory.collection,
      freshnessPolicy: discoveryFreshness,
      parser: (response) {
        final wire = DiscoveryWire.receive(
          response.jsonObject(),
          scope: 'personal',
        );
        final viewer = wire.data['viewer'];
        if (viewer is! Map || viewer['id'] != profileId) {
          throw const FormatException(
            'Discovery viewer does not match Profile',
          );
        }
        return AcquiredProjection(
          schemaVersion: 1,
          payload: wire.snapshotPayload,
          sourceGeneratedAt: DateTime.tryParse(
            wire.meta['generated_at'] as String? ?? '',
          ),
        );
      },
      applier: applyProjectionSnapshot,
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
    return SyncSourceDefinition(
      sourceKey: 'discovery-item:$family:$id',
      owner: 'Discovery',
      path: 'api/v1/discovery/items/$family/$id/',
      projectionKind: itemProjectionKind,
      resourceKey: '$family:$id',
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: detailFreshness,
      parser: (response) {
        final json = response.jsonObject();
        final envelope = ProjectionEnvelope.parse(
          json,
          expectedProjection: itemProjectionKind,
          expectedScope: 'personal',
        );
        final item = DiscoveryWire.receiveItem(json, scope: 'personal');
        final identity = item['identity'] as Map;
        final resource = identity['resource'] as Map;
        if (identity['family'] != family || resource['id'] != id) {
          throw const FormatException('Unexpected Discovery detail identity');
        }
        return AcquiredProjection(
          schemaVersion: envelope.schemaVersion,
          payload: {'item': item},
          sourceGeneratedAt: envelope.generatedAt,
        );
      },
      applier: applyProjectionSnapshot,
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

  /// Bounded, derived presentation window. Each item is an unchanged server
  /// wire fact; the client only drops older Discover rows, never ranks them.
  StoredProjection? _presentedProjection(
    DiscoveryQuery query,
    StoredProjection window,
  ) {
    final payload = window.payload;
    final field = payload['field'];
    if (field is! Map<String, dynamic>) return null;
    final actor = field['viewer'];
    if (actor is Map && actor['id'] != profileId) return null;
    return StoredProjection(
      kind: itemsProjectionKind,
      resourceKey: query.fingerprint,
      schemaVersion: 1,
      payload: field,
      receivedAt: window.receivedAt,
      sourceGeneratedAt: window.sourceGeneratedAt,
      sourceUpdatedAt: window.sourceUpdatedAt,
      lastVerifiedOnlineAt: window.lastVerifiedOnlineAt,
      freshUntil: window.freshUntil,
      expiresAt: window.expiresAt,
      freshnessPolicyId: window.freshnessPolicyId,
    );
  }

  /// Store only the last fifty presented Discover candidates. A fresh
  /// continuation can compose with this window even after older transport
  /// pages have been dropped. The initial server page is always retained.
  Future<void> retainPresentedWindow(DiscoveryQuery query) async {
    if (query.page < 2) return;
    final projection = await readItems(query);
    if (projection == null) return;
    const selector = DiscoverySelector();
    final collection = selector.collection(projection);
    if (collection.page != query.page) return;
    final rows = collection.items;
    final bounded = rows.skip(
      rows.length > maxPresentedWindowItems
          ? rows.length - maxPresentedWindowItems
          : 0,
    ).map((item) => item.wire).toList(growable: false);
    final previous = await store.readProjection(
      presentedWindowKind,
      resourceKey: query.mapFingerprint,
    );
    // A fresh first-page acquisition starts a new server field. Do not
    // concatenate its candidates with a window from a previous field.
    final root = await store.readProjection(
      itemsProjectionKind,
      resourceKey: query.copyWith(page: 1, clearContinuation: true).fingerprint,
    );
    if (root == null) return;
    final wire = Map<String, dynamic>.from(collection.wire)
      ..['results'] = bounded
      ..['items'] = bounded;
    await store.putProjection(
      kind: presentedWindowKind,
      resourceKey: query.mapFingerprint,
      schemaVersion: 1,
      payload: {
        'page': query.page,
        'fingerprint': query.fingerprint,
        'field': wire,
      },
    );
    final oldPage = previous?.payload['page'];
    final oldKey = previous?.payload['fingerprint'];
    if (oldPage is int &&
        oldPage > 1 &&
        oldPage < query.page &&
        oldKey is String &&
        oldKey != query.fingerprint) {
      await store.deleteProjection(itemsProjectionKind, resourceKey: oldKey);
    }
  }

  /// A read-only logical field: each server page remains stored unchanged
  /// under its own criteria/cursor key. Presentation receives reconciled
  /// candidate identities, not a second persisted collection truth.
  Stream<StoredProjection?> watchItems(DiscoveryQuery query) {
    final updates = store.watchProjection(
      itemsProjectionKind,
      resourceKey: query.fingerprint,
    );
    if (query.page <= 1) return updates;
    return updates.asyncMap(
      (current) => _logicalItemsProjection(query, current),
    );
  }

  Future<StoredProjection?> _logicalItemsProjection(
    DiscoveryQuery query,
    StoredProjection? current,
  ) async {
    const selector = DiscoverySelector();
    final source = await readSource(itemsSource(query));
    if (source.ownerUnavailable) return null;
    // A revoked first-page field cannot be resurrected by a derived window,
    // even if a later cursor still has locally cached rows.
    final rootQuery = query.copyWith(page: 1, clearContinuation: true);
    final rootSource = await readSource(itemsSource(rootQuery));
    if (rootSource.ownerUnavailable) return null;
    final window = await store.readProjection(
      presentedWindowKind,
      resourceKey: query.mapFingerprint,
    );
    final windowPage = window?.payload['page'];
    if (window != null && windowPage is int) {
      final retained = _presentedProjection(query, window);
      if (retained != null) {
        if (windowPage == query.page &&
            window.payload['fingerprint'] == query.fingerprint &&
            (current == null ||
                !current.receivedAt.isAfter(window.receivedAt))) {
          return retained;
        }
        if (windowPage == query.page - 1 && current != null) {
          try {
            final earlier = selector.collection(retained);
            final incoming = selector.collection(current);
            final composed = earlier.reconcile(incoming);
            return StoredProjection(
              kind: itemsProjectionKind,
              resourceKey: query.fingerprint,
              schemaVersion: current.schemaVersion,
              payload: composed.wire,
              receivedAt: current.receivedAt,
              sourceGeneratedAt: current.sourceGeneratedAt,
              sourceUpdatedAt: current.sourceUpdatedAt,
              lastVerifiedOnlineAt: current.lastVerifiedOnlineAt,
              freshUntil: current.freshUntil,
              expiresAt: current.expiresAt,
              freshnessPolicyId: current.freshnessPolicyId,
            );
          } on FormatException {
            return current;
          }
        }
      }
    }
    DiscoveryCollectionPresentation? field;
    StoredProjection? last;
    var earlierQuery = query.copyWith(page: 1);
    try {
      for (var page = 1; page <= query.page; page++) {
        final projection = page == query.page
            ? current
            : await _readStoredItems(earlierQuery);
        // A missing lot cannot be represented by its preceding lot.
        // Keep the requested page absent (or return its own raw snapshot)
        // rather than mislabelling an incomplete offline field.
        if (projection == null) return current;
        final viewer = projection.payload['viewer'];
        if (viewer != null && (viewer is! Map || viewer['id'] != profileId)) {
          throw const FormatException(
            'Discovery snapshot belongs to another Profile',
          );
        }
        final batch = selector.collection(projection);
        if (batch.page != page) {
          throw const FormatException('Unexpected Discovery snapshot page');
        }
        field = field == null ? batch : field.reconcile(batch);
        last = projection;
        if (page < query.page) {
          earlierQuery = earlierQuery.copyWith(
            page: page + 1,
            continuation: batch.continuationToken,
          );
        }
      }
    } on FormatException {
      // An incompatible historical prefix cannot contaminate the current
      // server-owned page. The caller still sees its actual snapshot/error.
      return current;
    }
    if (last == null || field == null) return current;
    return StoredProjection(
      kind: last.kind,
      resourceKey: last.resourceKey,
      schemaVersion: last.schemaVersion,
      payload: field.wire,
      receivedAt: last.receivedAt,
      sourceGeneratedAt: last.sourceGeneratedAt,
      sourceUpdatedAt: last.sourceUpdatedAt,
      lastVerifiedOnlineAt: last.lastVerifiedOnlineAt,
      freshUntil: last.freshUntil,
      expiresAt: last.expiresAt,
      freshnessPolicyId: last.freshnessPolicyId,
    );
  }

  Future<StoredProjection?> _readStoredItems(DiscoveryQuery query) =>
      store.readProjection(itemsProjectionKind, resourceKey: query.fingerprint);

  /// Keep one-shot offline reads consistent with the watched logical field.
  /// Each raw server page remains the only persisted snapshot.
  Future<StoredProjection?> readItems(DiscoveryQuery query) async {
    final current = await _readStoredItems(query);
    if (query.page <= 1) return current;
    return _logicalItemsProjection(query, current);
  }

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
    final source = itemsSource(query);
    await _refresh(source);
    // A failed offline refresh retains the cached collection, but must not
    // re-index it as if fresh server data had just been received.
    if ((await readSource(source)).lastErrorCode == null) {
      await indexItemPreviews(query);
    }
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
    final source = activitySource(id);
    await _refresh(source);
    final state = await readSource(source);
    if (state.ownerUnavailable) {
      await store.deleteProjection(
        activityPreviewProjectionKind,
        resourceKey: id,
      );
    }
    if (state.lastErrorCode != null) return;
    final projection = await readActivity(id);
    if (projection != null) {
      await _indexActivityOccurrencePreviews(id, projection);
    }
  }

  Future<void> refreshOccurrence(String id) async {
    final source = occurrenceSource(id);
    await _refresh(source);
    if ((await readSource(source)).ownerUnavailable) {
      await store.deleteProjection(
        occurrencePreviewProjectionKind,
        resourceKey: id,
      );
    }
  }

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
    if (projection.schemaVersion != 1) {
      throw const FormatException('Unsupported Discovery snapshot version');
    }
    DiscoveryWire.validateData(projection.payload);
    final rawResults =
        projection.payload['results'] ?? projection.payload['items'];
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
