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
import 'discovery_unseen_reserve.dart';
import 'discovery_wire.dart';

class DiscoveryQuery {
  const DiscoveryQuery({
    this.text = '',
    this.spaceSlug,
    this.spaceId,
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

  /// Recreate an exploration context from a deep-link or map route, never
  /// from the map's own independent search model.
  factory DiscoveryQuery.fromRouteParameters(Map<String, String> params) {
    double? coordinate(String name, double minimum, double maximum) {
      final raw = params[name];
      if (raw == null) return null;
      final parsed = double.tryParse(raw);
      if (parsed == null ||
          !parsed.isFinite ||
          parsed < minimum ||
          parsed > maximum) {
        return null;
      }
      return parsed;
    }

    int positive(String name, int fallback, int maximum) {
      final value = int.tryParse(params[name] ?? '');
      return value != null && value >= 1 && value <= maximum ? value : fallback;
    }

    final lat = coordinate('lat', -90, 90);
    final lon = coordinate('lon', -180, 180);
    final radius = coordinate('radius_km', 0, 100000);
    final hasSpatial =
        params.containsKey('lat') ||
        params.containsKey('lon') ||
        params.containsKey('radius_km');
    final validLocation =
        lat != null &&
        lon != null &&
        (!params.containsKey('radius_km') || radius != null);
    if (hasSpatial && !validLocation) {
      throw const FormatException('Invalid spatial Discovery filters');
    }
    final page = positive('page', 1, 1000000);
    final continuation = params['continuation'];
    if (page > 1 && (continuation == null || continuation.isEmpty)) {
      throw const FormatException('Missing signed Discovery continuation');
    }
    final context = params['context'];
    final spaceSlug = params['space'];
    if ((context == 'space') != (spaceSlug != null && spaceSlug.isNotEmpty) ||
        (context != null && context != 'space' && context != 'personal')) {
      throw const FormatException('Invalid Discovery actor context');
    }
    return DiscoveryQuery(
      spaceSlug: context == 'space' ? spaceSlug : null,
      text: params['q'] ?? '',
      place: params['place'] ?? '',
      when: params['when'] ?? '',
      period: params['period'] ?? '',
      vertical: params['vertical'] ?? '',
      price: params['price'] ?? '',
      date: params['date'] ?? '',
      dateFrom: params['date_from'] ?? '',
      dateTo: params['date_to'] ?? '',
      latitude: validLocation ? lat : null,
      longitude: validLocation ? lon : null,
      radiusKm: validLocation ? radius : null,
      page: page > 1 && continuation != null && continuation.isNotEmpty
          ? page
          : 1,
      pageSize: positive('page_size', 24, 100),
      continuation: page > 1 && continuation != null && continuation.isNotEmpty
          ? continuation
          : null,
    );
  }

  /// All criteria, current page and opaque server continuation are transported
  /// unchanged to Map; UI-only selection is not sent to the API.
  String routeLocation(String screen, {String? selectedCandidateKey}) {
    final params = <String, String>{
      ...parameters,
      if (selectedCandidateKey != null && selectedCandidateKey.isNotEmpty)
        'selected': selectedCandidateKey,
    }..remove('timezone');
    return Uri(path: screen, queryParameters: params).toString();
  }

  /// The Space identity is resolved by the existing actor selector, never
  /// accepted from a URL as an authority assertion.
  final String? spaceSlug;
  final String? spaceId;
  bool get isSpace => spaceSlug != null;

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
    String? spaceSlug,
    String? spaceId,
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
      spaceSlug: spaceSlug ?? this.spaceSlug,
      spaceId: spaceId ?? this.spaceId,
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

  /// Watch is a separate owner action. Never persist technical page/cursor,
  /// freshness, viewer, or client map selection as Watch criteria.
  Map<String, String> get watchCriteria {
    const allowed = {
      'q',
      'place',
      'when',
      'period',
      'vertical',
      'price',
      'date',
      'date_from',
      'date_to',
      'lat',
      'lon',
      'radius_km',
      'timezone',
    };
    return Map<String, String>.unmodifiable({
      for (final entry in parameters.entries)
        if (allowed.contains(entry.key) && entry.value.trim().isNotEmpty)
          entry.key:
              entry.key == 'radius_km' &&
                  radiusKm != null &&
                  radiusKm! == radiusKm!.roundToDouble()
              ? radiusKm!.round().toString()
              : entry.value.trim(),
    });
  }

  Map<String, String> get parameters {
    return <String, String>{
      if (isSpace) 'context': 'space',
      if (spaceSlug != null) 'space': spaceSlug!,
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

  String get fingerprint => base64Url
      .encode(
        utf8.encode(
          isSpace
              ? '${spaceId ?? 'unresolved'}:$canonicalQuery'
              : canonicalQuery,
        ),
      )
      .replaceAll('=', '');

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

  String get mapFingerprint => base64Url
      .encode(
        utf8.encode(
          isSpace
              ? '${spaceId ?? 'unresolved'}:$mapCanonicalQuery'
              : mapCanonicalQuery,
        ),
      )
      .replaceAll('=', '');

  String get mapPath {
    final query = mapCanonicalQuery;
    return query.isEmpty
        ? 'api/v1/discovery/map/'
        : 'api/v1/discovery/map/?$query';
  }
}

/// Non-persistent result of a user-invoked Discovery owner action.
class DiscoveryClarification {
  const DiscoveryClarification({
    required this.status,
    required this.criteria,
    this.reason = '',
  });

  final String status;
  final Map<String, String> criteria;
  final String reason;
}

/// Sources are transient external leads, never canonical Discovery objects.
class DiscoverySourceLead {
  const DiscoverySourceLead({
    required this.label,
    required this.summary,
    required this.title,
    required this.url,
  });

  final String label;
  final String summary;
  final String title;
  final Uri url;
}

class DiscoverySourceResearch {
  const DiscoverySourceResearch({
    required this.status,
    required this.leads,
    this.reason = '',
  });

  final String status;
  final List<DiscoverySourceLead> leads;
  final String reason;
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
  static const unseenReserveKind = 'discovery.unseen-reserve';
  static const int maxPresentedWindowItems = 50;
  static const int maxCachedTransportPages = 48;
  static const int maxCachedDiscoveryDetails = 80;
  static const int maxCachedDiscoveryPreviews = 120;
  static const int maxCachedWatchResults = 24;
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

  /// Coalesce the same owner request across N1, Carte and N2.
  final Map<String, Future<void>> _inflightOwnerRefreshes = {};

  /// No offline queue or persistence: research is billed only by an explicit
  /// owner call and its results stay contextual to this search.
  Future<DiscoverySourceResearch> researchSources(String text) async {
    final response = (await api.post(
      'api/v1/discovery/research/',
      body: {'q': text.trim()},
    )).jsonObject();
    final meta = response['meta'];
    final data = response['data'];
    if (meta is! Map ||
        meta['projection'] != 'discovery.source-leads' ||
        data is! Map ||
        data['status'] is! String ||
        data['candidates'] is! List) {
      throw const FormatException('Invalid Discovery external source contract');
    }
    final leads = <DiscoverySourceLead>[];
    for (final row in data['candidates'] as List) {
      if (row is! Map || row['sources'] is! List) continue;
      final label = row['label'];
      final summary = row['summary'];
      if (label is! String || summary is! String) continue;
      for (final source in row['sources'] as List) {
        if (source is! Map || source['url'] is! String) continue;
        final url = Uri.tryParse(source['url'] as String);
        if (url == null ||
            url.scheme != 'https' ||
            url.host.isEmpty ||
            url.userInfo.isNotEmpty) {
          continue;
        }
        leads.add(
          DiscoverySourceLead(
            label: label,
            summary: summary,
            title: source['title'] is String
                ? source['title'] as String
                : url.host,
            url: url,
          ),
        );
        if (leads.length >= 6) break;
      }
      if (leads.length >= 6) break;
    }
    return DiscoverySourceResearch(
      status: data['status'] as String,
      leads: List.unmodifiable(leads),
      reason: data['reason'] is String ? data['reason'] as String : '',
    );
  }

  /// One explicit server-side Intelligence attempt; never stored in Drift,
  /// an outbox, or the Profile's projection history.
  Future<DiscoveryClarification> clarifySearch(DiscoveryQuery query) async {
    const allowed = {
      'q',
      'place',
      'when',
      'period',
      'vertical',
      'price',
      'date',
      'date_from',
      'date_to',
      'timezone',
      'lat',
      'lon',
      'radius_km',
    };
    final input = <String, String>{
      for (final entry in query.parameters.entries)
        if (allowed.contains(entry.key)) entry.key: entry.value,
    };
    final response = (await api.post(
      'api/v1/discovery/clarify/',
      body: {'criteria': input},
    )).jsonObject();
    if (response['meta'] is! Map ||
        (response['meta'] as Map)['projection'] != 'discovery.clarification') {
      throw const FormatException('Unexpected Discovery clarification owner');
    }
    final data = response['data'];
    if (data is! Map) {
      throw const FormatException('Invalid Discovery clarification');
    }
    final status = data['status'];
    final criteria = data['query'];
    if (status is! String || criteria is! Map) {
      throw const FormatException('Invalid clarification payload');
    }
    final parsed = <String, String>{};
    for (final entry in criteria.entries) {
      if (entry.key is! String ||
          !allowed.contains(entry.key) ||
          entry.value is! String) {
        throw const FormatException('Invalid clarification criteria');
      }
      parsed[entry.key as String] = entry.value as String;
    }
    return DiscoveryClarification(
      status: status,
      criteria: parsed,
      reason: data['reason'] is String ? data['reason'] as String : '',
    );
  }

  // Ephemeral navigation context owned by this Profile-specific repository.
  // No candidate list, permission or server continuation is invented here.
  DiscoveryQuery activeExploration = const DiscoveryQuery();

  void rememberExploration(DiscoveryQuery query) {
    activeExploration = query;
  }

  SyncSourceDefinition itemsSource(DiscoveryQuery query) {
    if (query.isSpace && (query.spaceId == null || query.spaceId!.isEmpty)) {
      throw const FormatException('Missing verified Space actor');
    }
    return SyncSourceDefinition(
      sourceKey: 'discovery:${query.fingerprint}',
      owner: 'Discovery',
      path: query.page == 1
          ? '${query.path}${query.path.contains('?') ? '&' : '?'}include_spatial_index=compact'
          : query.path,
      projectionKind: itemsProjectionKind,
      resourceKey: query.fingerprint,
      category: SyncSourceCategory.collection,
      freshnessPolicy: discoveryFreshness,
      parser: (response) {
        final wire = DiscoveryWire.receive(
          response.jsonObject(),
          scope: query.isSpace ? 'space' : 'personal',
          expectedSpaceId: query.spaceId,
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

  /// Map presentation of the same canonical Discovery candidates, not a
  /// separate search or detail owner. Cached by viewer-scoped exploration.
  SyncSourceDefinition spatialSource(DiscoveryQuery query) {
    final path = query.mapPath;
    return SyncSourceDefinition(
      sourceKey: 'discovery-map-spatial:${query.mapFingerprint}',
      owner: 'Discovery',
      path: '$path${path.contains('?') ? '&' : '?'}spatial=1',
      projectionKind: mapProjectionKind,
      resourceKey: 'spatial:${query.mapFingerprint}',
      category: SyncSourceCategory.collection,
      freshnessPolicy: discoveryFreshness,
      parser: (response) {
        final payload = response.jsonObject();
        if (payload['results'] is! List || payload['count'] is! int) {
          throw const FormatException('Invalid Discovery spatial presentation');
        }
        // A legacy map response contains coordinates but no canonical
        // identities. Reject it rather than silently rendering an empty map.
        DiscoveryWire.validateData(payload);
        return AcquiredProjection(schemaVersion: 1, payload: payload);
      },
      applier: applyProjectionSnapshot,
    );
  }

  String _detailResourceKey(
    String family,
    String id,
    DiscoveryQuery actorQuery,
  ) => actorQuery.isSpace
      ? 'space:${actorQuery.spaceId}:$family:$id'
      : '$family:$id';

  SyncSourceDefinition itemSource(
    String family,
    String id, {
    DiscoveryQuery actorQuery = const DiscoveryQuery(),
  }) {
    if (actorQuery.isSpace &&
        (actorQuery.spaceId == null || actorQuery.spaceId!.isEmpty)) {
      throw const FormatException('Missing verified Space actor for detail');
    }
    final resourceKey = _detailResourceKey(family, id, actorQuery);
    final actorParams = actorQuery.isSpace
        ? '?context=space&space=${Uri.encodeQueryComponent(actorQuery.spaceSlug!)}'
        : '';
    return SyncSourceDefinition(
      sourceKey: 'discovery-item:$resourceKey',
      owner: 'Discovery',
      path: 'api/v1/discovery/items/$family/$id/$actorParams',
      projectionKind: itemProjectionKind,
      resourceKey: resourceKey,
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: detailFreshness,
      parser: (response) {
        final json = response.jsonObject();
        final envelope = ProjectionEnvelope.parse(
          json,
          expectedProjection: itemProjectionKind,
          expectedScope: actorQuery.isSpace ? 'space' : 'personal',
        );
        final item = DiscoveryWire.receiveItem(
          json,
          scope: actorQuery.isSpace ? 'space' : 'personal',
          expectedSpaceId: actorQuery.spaceId,
          expectedViewerId: profileId,
        );
        final identity = item['identity'] as Map;
        final resource = identity['resource'] as Map;
        if (identity['family'] != family || resource['id'] != id) {
          throw const FormatException('Unexpected Discovery detail identity');
        }
        return AcquiredProjection(
          schemaVersion: envelope.schemaVersion,
          payload: {
            'item': item,
            if (actorQuery.isSpace) ...{
              'actor': envelope.data['actor'],
              'viewer': envelope.data['viewer'],
            },
          },
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
      indexedResourceKind: 'Activity',
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
      indexedResourceKind: 'Occurrence',
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

  Future<DiscoveryUnseenReserve?> readUnseenReserve(
    DiscoveryQuery query,
  ) async {
    final rootQuery = query.copyWith(page: 1, clearContinuation: true);
    if ((await readSource(itemsSource(rootQuery))).ownerUnavailable) {
      return null;
    }
    final root = await _readStoredItems(rootQuery);
    if (root == null) return null;
    final saved = await store.readProjection(
      unseenReserveKind,
      resourceKey: query.mapFingerprint,
    );
    if (saved == null || saved.schemaVersion != 1) return null;
    return DiscoveryUnseenReserve.fromPayload(
      saved.payload,
      profileId: profileId,
      fieldKey: query.mapFingerprint,
      rootReceivedAt: root.receivedAt,
    );
  }

  Future<void> _unseenWrite = Future<void>.value();

  Future<void> saveUnseenReserve(
    DiscoveryQuery query,
    DiscoveryUnseenReserve reserve,
  ) async {
    final rootQuery = query.copyWith(page: 1, clearContinuation: true);
    if ((await readSource(itemsSource(rootQuery))).ownerUnavailable) return;
    final root = await _readStoredItems(rootQuery);
    if (root == null ||
        reserve.rootReceivedAt == null ||
        reserve.rootReceivedAt != root.receivedAt) {
      return;
    }
    final payload = reserve.toPayload(
      profileId: profileId,
      fieldKey: query.mapFingerprint,
      rootReceivedAt: root.receivedAt,
    );
    // User reveals and invisible prefetch may both update the ledger.
    // Serialize their durable writes in presentation order.
    final write = _unseenWrite
        .catchError((Object _) {})
        .then(
          (_) => store.putProjection(
            kind: unseenReserveKind,
            resourceKey: query.mapFingerprint,
            schemaVersion: 1,
            payload: payload,
            receivedAt: root.receivedAt,
            sourceGeneratedAt: root.sourceGeneratedAt,
          ),
        );
    _unseenWrite = write;
    await write;
  }

  /// Bounded, derived presentation window. Each item is an unchanged server
  /// wire fact; the client only drops older Discover rows, never ranks them.
  StoredProjection? _presentedProjection(
    DiscoveryQuery query,
    StoredProjection window,
  ) {
    final payload = window.payload;
    final field = payload['field'];
    if (field is! Map<String, dynamic> ||
        window.schemaVersion != 1 ||
        window.payload['fingerprint'] is! String) {
      return null;
    }
    final actor = field['viewer'];
    if (actor is! Map || actor['id'] != profileId) return null;
    final scopeActor = field['actor'];
    if (query.isSpace) {
      if (field['surface'] != 'discover_space' ||
          scopeActor is! Map ||
          scopeActor['type'] != 'space' ||
          scopeActor['id'] != query.spaceId)
        return null;
    } else {
      if (field['surface'] != 'discover_me' ||
          scopeActor is! Map ||
          scopeActor['type'] != 'profile' ||
          scopeActor['id'] != profileId)
        return null;
    }
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
    final bounded = rows
        .skip(
          rows.length > maxPresentedWindowItems
              ? rows.length - maxPresentedWindowItems
              : 0,
        )
        .map((item) => item.wire)
        .toList(growable: false);
    final previous = await store.readProjection(
      presentedWindowKind,
      resourceKey: query.mapFingerprint,
    );
    // A fresh first-page acquisition starts a new server field. Do not
    // concatenate its candidates with a window from a previous field.
    final root = await _readStoredItems(
      query.copyWith(page: 1, clearContinuation: true),
    );
    if (root == null ||
        root.payload['viewer'] is! Map ||
        (root.payload['viewer'] as Map)['id'] != profileId) {
      return;
    }
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
      receivedAt: projection.receivedAt,
      sourceGeneratedAt: projection.sourceGeneratedAt,
      lastVerifiedOnlineAt: projection.lastVerifiedOnlineAt,
      freshnessPolicyId: discoveryFreshness.id,
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
    return updates.asyncMap(
      (current) => query.page <= 1
          ? _readAvailable(
              itemsSource(query),
              current,
              expectedSpaceId: query.spaceId,
            )
          : _logicalItemsProjection(query, current),
    );
  }

  Future<StoredProjection?> _logicalItemsProjection(
    DiscoveryQuery query,
    StoredProjection? current,
  ) async {
    const selector = DiscoverySelector();
    final source = await readSource(itemsSource(query));
    if (source.ownerUnavailable) return null;
    current = await _readAvailable(
      itemsSource(query),
      current,
      expectedSpaceId: query.spaceId,
    );
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
    // A new root acquisition invalidates the history of a former signed
    // cursor even when its displayed criteria did not change.
    final currentRoot = await _readStoredItems(rootQuery);
    if (window != null &&
        windowPage is int &&
        currentRoot != null &&
        !currentRoot.receivedAt.isAfter(window.receivedAt)) {
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

  /// Owner 403/404 is a tombstone, not an offline stale snapshot. All local
  /// reads (including root, map and N2) must pass this gate.
  Future<StoredProjection?> _readAvailable(
    SyncSourceDefinition source,
    StoredProjection? snapshot, {
    String? expectedSpaceId,
  }) async {
    if (snapshot == null) return null;
    if ((await readSource(source)).ownerUnavailable) return null;
    if (source.projectionKind == itemsProjectionKind) {
      final viewer = snapshot.payload['viewer'];
      final actor = snapshot.payload['actor'];
      final surface = snapshot.payload['surface'];
      if (snapshot.schemaVersion != 1 ||
          viewer is! Map ||
          viewer['id'] != profileId ||
          (expectedSpaceId != null
              ? surface != 'discover_space'
              : surface != 'discover_me') ||
          actor is! Map ||
          (surface == 'discover_space' &&
              (actor['type'] != 'space' ||
                  expectedSpaceId == null ||
                  actor['id'] != expectedSpaceId)) ||
          (surface == 'discover_me' &&
              (actor['type'] != 'profile' || actor['id'] != profileId))) {
        return null;
      }
      try {
        DiscoveryWire.validateData(snapshot.payload);
      } on FormatException {
        return null;
      }
    }
    if (source.projectionKind == itemProjectionKind) {
      final item = snapshot.payload['item'];
      final identity = item is Map ? item['identity'] : null;
      final actor = snapshot.payload['actor'];
      final viewer = snapshot.payload['viewer'];
      if (snapshot.schemaVersion != 1 ||
          identity is! Map ||
          identity['family'] is! String ||
          identity['resource'] is! Map ||
          (expectedSpaceId == null
                  ? '${identity['family']}:${(identity['resource'] as Map)['id']}'
                  : 'space:$expectedSpaceId:${identity['family']}:${(identity['resource'] as Map)['id']}') !=
              source.resourceKey ||
          (expectedSpaceId != null &&
              (actor is! Map ||
                  actor['type'] != 'space' ||
                  actor['id'] != expectedSpaceId ||
                  viewer is! Map ||
                  viewer['type'] != 'profile' ||
                  viewer['id'] != profileId))) {
        return null;
      }
      try {
        DiscoveryWire.validateData({
          'results': [item],
        });
      } on FormatException {
        return null;
      }
    }
    if (snapshot.expiresAt != null &&
        !DateTime.now().toUtc().isBefore(snapshot.expiresAt!.toUtc())) {
      return null;
    }
    return snapshot;
  }

  Future<StoredProjection?> _readStoredItems(DiscoveryQuery query) async =>
      _readAvailable(
        itemsSource(query),
        await store.readProjection(
          itemsProjectionKind,
          resourceKey: query.fingerprint,
        ),
        expectedSpaceId: query.spaceId,
      );

  /// Keep one-shot offline reads consistent with the watched logical field.
  /// Each raw server page remains the only persisted snapshot.
  Future<StoredProjection?> readItems(DiscoveryQuery query) async {
    final current = await _readStoredItems(query);
    if (query.page <= 1) return current;
    return _logicalItemsProjection(query, current);
  }

  /// A first-page Discovery snapshot is also the spatial field's source of
  /// truth. The map never owns an additional search, ranking or persistence.
  StoredProjection? _spatialFromField(StoredProjection? field) {
    if (field == null || field.schemaVersion != 1) return null;
    final raw = field.payload['spatial_index'];
    if (raw is! Map) {
      return null; // Older servers remain explicitly unsupported.
    }
    final index = Map<String, dynamic>.from(raw);
    if (index['count'] is! int ||
        index['total_results'] is! int ||
        index['results'] is! List ||
        index['detail_available'] is! bool ||
        index['viewer'] is! Map ||
        (index['viewer'] as Map)['id'] != profileId) {
      return null;
    }
    try {
      DiscoveryWire.validateData(index);
    } on FormatException {
      return null;
    }
    return StoredProjection(
      kind: mapProjectionKind,
      resourceKey: 'spatial:${field.resourceKey}',
      schemaVersion: field.schemaVersion,
      payload: index,
      receivedAt: field.receivedAt,
      sourceGeneratedAt: field.sourceGeneratedAt,
      sourceUpdatedAt: field.sourceUpdatedAt,
      lastVerifiedOnlineAt: field.lastVerifiedOnlineAt,
      freshUntil: field.freshUntil,
      expiresAt: field.expiresAt,
      freshnessPolicyId: field.freshnessPolicyId,
    );
  }

  /// Caller-owned freshness for *display*, never a promise of live
  /// Capacity/Access/Payment. Explicit refresh and mutations still hit owner.
  bool _freshEnough(StoredProjection? projection, Duration age) {
    if (projection == null) return false;
    final observed = projection.lastVerifiedOnlineAt ?? projection.receivedAt;
    return !DateTime.now().toUtc().difference(observed.toUtc()).isNegative &&
        DateTime.now().toUtc().difference(observed.toUtc()) <= age;
  }

  Future<bool> hasReusableItems(
    DiscoveryQuery query, {
    bool requireSpatial = false,
  }) async {
    final snapshot = await readItems(query);
    if (!_freshEnough(snapshot, discoveryFreshness.refreshRecommendedAfter!)) {
      return false;
    }
    final state = await readSource(itemsSource(query));
    if (state.invalidated ||
        state.lastErrorCode != null ||
        state.lastSuccessAt == null) {
      return false;
    }
    return !requireSpatial || _spatialFromField(snapshot) != null;
  }

  /// N1 and Carte share this acquisition. Do not force another HTTP request
  /// solely because the user switched to another presentation.
  Future<void> ensureItems(
    DiscoveryQuery query, {
    bool requireSpatial = false,
  }) async {
    if (await hasReusableItems(query, requireSpatial: requireSpatial)) return;
    await refreshItems(query);
  }

  Future<bool> hasReusableActivity(String id) async {
    final projection = await readActivity(id);
    if (!_freshEnough(projection, detailFreshness.refreshRecommendedAfter!)) {
      return false;
    }
    final state = await readSource(activitySource(id));
    return !state.invalidated &&
        state.lastErrorCode == null &&
        projection?.payload['identity'] is Map &&
        (projection!.payload['identity'] as Map)['id'] == id;
  }

  Future<bool> hasReusableOccurrenceForReading(String id) async {
    final state = await readSource(occurrenceSource(id));
    if (state.invalidated || state.lastErrorCode != null) return false;
    final projection = await readOccurrence(id);
    final identity = projection?.payload['identity'];
    final caps = projection?.payload['capabilities'];
    // Any known live Day-of privilege requires an owner recheck on entry.
    if (caps is List && caps.contains('open_day_of')) return false;
    if (_freshEnough(projection, detailFreshness.refreshRecommendedAfter!) &&
        identity is Map &&
        identity['kind'] == 'occurrence' &&
        identity['id'] == id) {
      return true;
    }

    // Reading an admitted Occurrence's time and place is a presentation,
    // not a Day-of/Access decision. N1/N2 may already contain enough facts.
    final preview = await readOccurrencePreview(id);
    if (!_freshEnough(preview, detailFreshness.refreshRecommendedAfter!)) {
      return false;
    }
    final raw = preview?.payload['item'];
    final candidate = raw is Map ? raw['identity'] : null;
    final occurrence = candidate is Map ? candidate['occurrence'] : null;
    if (occurrence is Map &&
        occurrence['kind'] == 'occurrence' &&
        occurrence['id'] == id) {
      return true;
    }
    final summary = preview?.payload['occurrence'];
    return summary is Map && summary['id'] == id;
  }

  Stream<StoredProjection?> watchMap(DiscoveryQuery query) => store
      .watchProjection(mapProjectionKind, resourceKey: query.mapFingerprint)
      .asyncMap((row) => _readAvailable(mapSource(query), row));

  Future<StoredProjection?> readMap(DiscoveryQuery query) async =>
      _readAvailable(
        mapSource(query),
        await store.readProjection(
          mapProjectionKind,
          resourceKey: query.mapFingerprint,
        ),
      );

  Stream<StoredProjection?> watchSpatial(DiscoveryQuery query) {
    final first = query.copyWith(page: 1, clearContinuation: true);
    return watchItems(first).map(_spatialFromField);
  }

  Future<StoredProjection?> readSpatial(DiscoveryQuery query) async {
    final first = query.copyWith(page: 1, clearContinuation: true);
    return _spatialFromField(await readItems(first));
  }

  Stream<StoredProjection?> watchItem(
    String family,
    String id, {
    DiscoveryQuery actorQuery = const DiscoveryQuery(),
  }) => store
      .watchProjection(
        itemProjectionKind,
        resourceKey: _detailResourceKey(family, id, actorQuery),
      )
      .asyncMap(
        (row) => _readAvailable(
          itemSource(family, id, actorQuery: actorQuery),
          row,
          expectedSpaceId: actorQuery.spaceId,
        ),
      );

  /// Materialize a previously acquired owner projection only on N2 demand.
  /// The server has already admitted it for this viewer: changing N1, Carte
  /// or N2 is not another admission request. Source revocations and TTLs win.
  Future<StoredProjection?> _itemFromAcquiredField(
    String family,
    String id, {
    DateTime? newerThan,
    DiscoveryQuery actorQuery = const DiscoveryQuery(),
  }) async {
    final owner = itemSource(family, id, actorQuery: actorQuery);
    final detailKey = _detailResourceKey(family, id, actorQuery);
    if ((await readSource(owner)).ownerUnavailable) return null;
    final pages = await store.readProjections(itemsProjectionKind);
    pages.sort((a, b) => b.receivedAt.compareTo(a.receivedAt));
    final now = DateTime.now().toUtc();

    for (final page in pages) {
      // A previous owner-confirmed detail or saved mutation always beats an
      // older collection. Never replace newer item facts with an old page.
      if (newerThan != null && !page.receivedAt.isAfter(newerThan)) {
        continue;
      }
      if (page.schemaVersion != 1 ||
          (page.expiresAt != null && !now.isBefore(page.expiresAt!.toUtc()))) {
        continue;
      }
      final viewer = page.payload['viewer'];
      if (viewer is! Map || viewer['id'] != profileId) continue;
      final pageActor = page.payload['actor'];
      if (actorQuery.isSpace) {
        if (page.payload['surface'] != 'discover_space' ||
            pageActor is! Map ||
            pageActor['type'] != 'space' ||
            pageActor['id'] != actorQuery.spaceId)
          continue;
      } else {
        if (page.payload['surface'] != 'discover_me') continue;
      }
      final sourceQuery = database.select(database.syncSources)
        ..where(
          (row) =>
              row.profileId.equals(profileId) &
              row.sourceKey.equals('discovery:${page.resourceKey}'),
        );
      final sourceRow = await sourceQuery.getSingleOrNull();
      if (sourceRow?.invalidated == true) continue;

      final collections = <Object?>[
        page.payload['results'],
        if (page.payload['spatial_index'] is Map &&
            (page.payload['spatial_index'] as Map)['detail_available'] ==
                true &&
            (page.payload['spatial_index'] as Map)['viewer'] is Map &&
            ((page.payload['spatial_index'] as Map)['viewer'] as Map)['id'] ==
                profileId)
          (page.payload['spatial_index'] as Map)['results'],
      ];
      for (final collection in collections) {
        if (collection is! List) continue;
        for (final raw in collection) {
          if (raw is! Map) continue;
          final identity = raw['identity'];
          final resource = identity is Map ? identity['resource'] : null;
          if (identity is! Map ||
              resource is! Map ||
              identity['family'] != family ||
              resource['id'] != id) {
            continue;
          }
          final item = Map<String, dynamic>.from(raw);
          try {
            DiscoveryWire.validateData({
              'results': [item],
            });
          } on FormatException {
            continue;
          }
          // Preserve the original acquisition's time and provenance. This
          // does not invent a successful item-detail owner HTTP response.
          await store.putProjection(
            kind: itemProjectionKind,
            resourceKey: detailKey,
            schemaVersion: page.schemaVersion,
            payload: {
              'item': item,
              if (actorQuery.isSpace) ...{'actor': pageActor, 'viewer': viewer},
            },
            receivedAt: page.receivedAt,
            sourceGeneratedAt: page.sourceGeneratedAt,
            sourceUpdatedAt: page.sourceUpdatedAt,
            lastVerifiedOnlineAt: page.lastVerifiedOnlineAt,
            freshUntil: page.freshUntil,
            expiresAt: page.expiresAt,
            freshnessPolicyId: page.freshnessPolicyId,
          );
          // The same already-admitted wire can present the read-only N3
          // preview. Actual owner operations are not authorized by it.
          if (!actorQuery.isSpace && _isActivityFamily(family)) {
            await _putPreview(
              kind: activityPreviewProjectionKind,
              resourceKey: id,
              payload: {'item': item},
              source: page,
            );
          }
          final occurrence = identity['occurrence'];
          if (!actorQuery.isSpace &&
              occurrence is Map &&
              occurrence['id'] is String &&
              (occurrence['id'] as String).isNotEmpty) {
            await _putPreview(
              kind: occurrencePreviewProjectionKind,
              resourceKey: occurrence['id'] as String,
              payload: {'item': item},
              source: page,
            );
          }
          return _readAvailable(
            owner,
            await store.readProjection(
              itemProjectionKind,
              resourceKey: detailKey,
            ),
            expectedSpaceId: actorQuery.spaceId,
          );
        }
      }
    }
    return null;
  }

  Future<StoredProjection?> readItem(
    String family,
    String id, {
    DiscoveryQuery actorQuery = const DiscoveryQuery(),
  }) async {
    final source = itemSource(family, id, actorQuery: actorQuery);
    final local = await _readAvailable(
      source,
      await store.readProjection(
        itemProjectionKind,
        resourceKey: _detailResourceKey(family, id, actorQuery),
      ),
      expectedSpaceId: actorQuery.spaceId,
    );
    if (local != null &&
        _freshEnough(local, detailFreshness.refreshRecommendedAfter!)) {
      return local;
    }
    final acquired = await _itemFromAcquiredField(
      family,
      id,
      newerThan: local?.receivedAt,
      actorQuery: actorQuery,
    );
    return acquired ?? local;
  }

  /// Query the owner only for absent/stale information. A server-projected
  /// N1/Carte detail is enough for presentation; real actions still use the
  /// owning authenticated endpoint, not the client-side capability alone.
  Future<bool> hasReusableItem(
    String family,
    String id, {
    DiscoveryQuery actorQuery = const DiscoveryQuery(),
  }) async {
    final item = await readItem(family, id, actorQuery: actorQuery);
    if (item == null || item.schemaVersion != 1) return false;
    final source = await readSource(
      itemSource(family, id, actorQuery: actorQuery),
    );
    if (source.invalidated || source.lastErrorCode != null) return false;
    final observed = item.lastVerifiedOnlineAt ?? item.receivedAt;
    final elapsed = DateTime.now().toUtc().difference(observed.toUtc());
    return !elapsed.isNegative &&
        elapsed <= detailFreshness.refreshRecommendedAfter!;
  }

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

  Stream<StoredProjection?> watchWatches() => store
      .watchProjection(watchesProjectionKind)
      .asyncMap((row) => _readAvailable(watchesSource(), row));

  Stream<StoredProjection?> watchWatchResults(String watchId, {int page = 1}) =>
      store
          .watchProjection(
            watchResultsProjectionKind,
            resourceKey: '$watchId:$page',
          )
          .asyncMap(
            (row) =>
                _readAvailable(watchResultsSource(watchId, page: page), row),
          );

  Future<StoredProjection?> readWatchResults(
    String watchId, {
    int page = 1,
  }) async => _readAvailable(
    watchResultsSource(watchId, page: page),
    await store.readProjection(
      watchResultsProjectionKind,
      resourceKey: '$watchId:$page',
    ),
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
    // A failed offline refresh retains existing data without re-indexing it.
    if ((await readSource(source)).lastErrorCode != null) return;
    if (query.page == 1) {
      // A newly signed first page supersedes any prior device-side
      // continuation window; old cursors are never replayed as current.
      await store.deleteProjection(
        presentedWindowKind,
        resourceKey: query.mapFingerprint,
      );
      await store.deleteProjection(
        unseenReserveKind,
        resourceKey: query.mapFingerprint,
      );
    }
    await indexItemPreviews(query);
    final rootKey = query
        .copyWith(page: 1, clearContinuation: true)
        .fingerprint;
    await store.pruneProjectionsOfKind(
      itemsProjectionKind,
      retain: maxCachedTransportPages,
      protectResourceKeys: {query.fingerprint, rootKey},
    );
    await store.pruneProjectionsOfKind(
      activityPreviewProjectionKind,
      retain: maxCachedDiscoveryPreviews,
    );
    await store.pruneProjectionsOfKind(
      occurrencePreviewProjectionKind,
      retain: maxCachedDiscoveryPreviews,
    );
  }

  Future<void> indexItemPreviews(DiscoveryQuery query) async {
    // Personal detail previews cannot be populated from a Space acquisition.
    if (query.isSpace) return;
    final projection = await readItems(query);
    if (projection == null) return;
    await _indexDiscoveryItemPreviews(projection);
  }

  Future<void> refreshMap(DiscoveryQuery query) async {
    await _refresh(mapSource(query));
    if ((await readSource(mapSource(query))).lastErrorCode == null) {
      await store.pruneProjectionsOfKind(
        mapProjectionKind,
        retain: 12,
        protectResourceKeys: {query.mapFingerprint},
      );
    }
  }

  Future<void> refreshSpatial(DiscoveryQuery query) async {
    final root = query.copyWith(page: 1, clearContinuation: true);
    await ensureItems(root, requireSpatial: true);
  }

  Future<void> refreshItem(
    String family,
    String id, {
    DiscoveryQuery actorQuery = const DiscoveryQuery(),
  }) async {
    final source = itemSource(family, id, actorQuery: actorQuery);
    await _refresh(source);
    if ((await readSource(source)).lastErrorCode == null) {
      await store.pruneProjectionsOfKind(
        itemProjectionKind,
        retain: maxCachedDiscoveryDetails,
        protectResourceKeys: {_detailResourceKey(family, id, actorQuery)},
      );
    }
  }

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

  Future<void> _forgetWatchResults(String watchId) async {
    final snapshots = await store.readProjections(watchResultsProjectionKind);
    for (final snapshot in snapshots) {
      if (snapshot.resourceKey.startsWith('$watchId:')) {
        await store.deleteProjection(
          watchResultsProjectionKind,
          resourceKey: snapshot.resourceKey,
        );
      }
    }
  }

  /// Reconcile only a fully owner-confirmed Watch row. This is a local read
  /// model update, never a fabricated Watch state or a new offline mutation.
  Future<void> _applyConfirmedWatch(Map? watch, {String? deletedId}) async {
    final existing = await store.readProjection(watchesProjectionKind);
    final previous = existing?.payload['results'];
    if (existing == null || previous is! List) return;
    final id = deletedId ?? watch?['id'];
    if (id is! String || id.isEmpty) return;
    final rows = <Map<String, dynamic>>[
      if (watch != null) Map<String, dynamic>.from(watch),
      for (final raw in previous)
        if (raw is Map && raw['id'] != id) Map<String, dynamic>.from(raw),
    ];
    await store.putProjection(
      kind: watchesProjectionKind,
      schemaVersion: existing.schemaVersion,
      payload: {...existing.payload, 'results': rows.take(100).toList()},
      receivedAt: existing.receivedAt,
      sourceGeneratedAt: existing.sourceGeneratedAt,
      lastVerifiedOnlineAt: existing.lastVerifiedOnlineAt,
      freshUntil: existing.freshUntil,
      expiresAt: existing.expiresAt,
      freshnessPolicyId: existing.freshnessPolicyId,
    );
  }

  /// A Watch is not Save, Share or owner Engagement. The API owns creation
  /// and deduplication; only its confirmed response may open a Watch screen.
  Future<String> createWatch({
    required String name,
    required DiscoveryQuery query,
  }) async {
    final criteria = query.watchCriteria;
    if (name.trim().isEmpty || name.trim().length > 140 || criteria.isEmpty) {
      throw const FormatException('Nom et critères de Veille requis');
    }
    final response = await api.post(
      'api/v1/discovery/watches/',
      body: {'name': name.trim(), 'criteria': criteria},
    );
    final envelope = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'discovery.watch',
    );
    final watch = envelope.data['watch'];
    if (watch is! Map ||
        watch['id'] is! String ||
        (watch['id'] as String).isEmpty ||
        watch['criteria'] is! Map) {
      throw const FormatException('Veille non confirmée par le serveur');
    }
    await _applyConfirmedWatch(watch);
    try {
      await refreshWatches();
    } on Object {
      // Watch identity was already confirmed; list sync is opportunistic.
    }
    return watch['id'] as String;
  }

  Future<void> updateWatchStatus(String id, String status) async {
    if (!const {'active', 'paused'}.contains(status)) {
      throw const FormatException('État de Veille inconnu');
    }
    final response = await api.patch(
      'api/v1/discovery/watches/${Uri.encodeComponent(id)}/',
      body: {'status': status},
    );
    final envelope = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'discovery.watch',
    );
    final watch = envelope.data['watch'];
    if (watch is! Map || watch['id'] != id || watch['status'] != status) {
      throw const FormatException('Transition de Veille non confirmée');
    }
    await _applyConfirmedWatch(watch);
    await _forgetWatchResults(id);
    try {
      await refreshWatches();
    } on Object {
      // Server status was already confirmed; do not imply a failed change.
    }
  }

  Future<void> editWatch(
    String id, {
    String? name,
    DiscoveryQuery? replaceCriteria,
  }) async {
    if (name == null && replaceCriteria == null) {
      throw const FormatException('Aucune modification de Veille demandée');
    }
    if (name != null && (name.trim().isEmpty || name.trim().length > 140)) {
      throw const FormatException('Nom de Veille invalide');
    }
    if (replaceCriteria != null && replaceCriteria.watchCriteria.isEmpty) {
      throw const FormatException('Critères de Veille manquants');
    }
    final response = await api.patch(
      'api/v1/discovery/watches/${Uri.encodeComponent(id)}/',
      body: {
        if (name != null) 'name': name.trim(),
        if (replaceCriteria != null) 'criteria': replaceCriteria.watchCriteria,
      },
    );
    final envelope = ProjectionEnvelope.parse(
      response.jsonObject(),
      expectedProjection: 'discovery.watch',
    );
    final watch = envelope.data['watch'];
    if (watch is! Map ||
        watch['id'] != id ||
        (name != null && watch['name'] != name.trim()) ||
        (replaceCriteria != null && watch['criteria'] is! Map)) {
      throw const FormatException('Édition de Veille non confirmée');
    }
    await _applyConfirmedWatch(watch);
    await _forgetWatchResults(id);
    try {
      await refreshWatches();
    } on Object {
      // The owner-confirmed edit remains valid without a refreshed list.
    }
  }

  Future<void> deleteWatch(String id) async {
    final response = await api.delete(
      'api/v1/discovery/watches/${Uri.encodeComponent(id)}/',
    );
    if (response.statusCode != 204) {
      throw const FormatException('Suppression de Veille non confirmée');
    }
    await _applyConfirmedWatch(null, deletedId: id);
    await _forgetWatchResults(id);
    try {
      await refreshWatches();
    } on Object {
      // Server deletion already confirmed; list can reconcile later.
    }
  }

  Future<void> refreshWatchResults(String watchId, {int page = 1}) async {
    final source = watchResultsSource(watchId, page: page);
    await _refresh(source);
    if ((await readSource(source)).lastErrorCode == null) {
      await store.pruneProjectionsOfKind(
        watchResultsProjectionKind,
        retain: maxCachedWatchResults,
        protectResourceKeys: {'$watchId:$page'},
      );
    }
  }

  /// Reconcile a *confirmed* Discovery owner mutation into cached personal
  /// collection windows. Their contents, ordering, filters and freshness do
  /// not change; this updates only the exact resource's saved capability.
  Future<void> _reconcileConfirmedSaved(
    String family,
    String id,
    Map<String, dynamic> confirmed,
  ) async {
    final saved = confirmed['saved'];
    final capabilities = confirmed['capabilities'];
    if (saved is! Map || capabilities is! List) return;

    // Patch only the exact owner-confirmed resource, without disturbing
    // ordering, relevance, geometry, other candidates or acquisition time.
    List<dynamic>? patchedRows(Object? input) {
      if (input is! List) return null;
      var changed = false;
      final rows = <dynamic>[];
      for (final raw in input) {
        if (raw is! Map) {
          rows.add(raw);
          continue;
        }
        final identity = raw['identity'];
        final resource = identity is Map ? identity['resource'] : null;
        if (identity is! Map ||
            resource is! Map ||
            identity['family'] != family ||
            resource['id'] != id) {
          rows.add(raw);
          continue;
        }
        rows.add({
          ...Map<String, dynamic>.from(raw),
          'saved': Map<String, dynamic>.from(saved),
          'capabilities': List<dynamic>.from(capabilities),
        });
        changed = true;
      }
      return changed ? rows : null;
    }

    final cached = await store.readProjections(itemsProjectionKind);
    for (final projection in cached) {
      if (projection.schemaVersion != 1) continue;
      final viewer = projection.payload['viewer'];
      if (viewer is! Map ||
          viewer['id'] != profileId ||
          projection.payload['surface'] != 'discover_me')
        continue;

      final payload = Map<String, dynamic>.from(projection.payload);
      var changed = false;
      final rows = patchedRows(payload['results'] ?? payload['items']);
      if (rows != null) {
        // The DiscoveryWire requires equal results/items aliases.
        if (payload['results'] is List) payload['results'] = rows;
        if (payload['items'] is List) payload['items'] = rows;
        changed = true;
      }
      final spatial = payload['spatial_index'];
      if (spatial is Map &&
          spatial['detail_available'] == true &&
          spatial['viewer'] is Map &&
          (spatial['viewer'] as Map)['id'] == profileId) {
        final indexRows = patchedRows(spatial['results']);
        if (indexRows != null) {
          payload['spatial_index'] = {
            ...Map<String, dynamic>.from(spatial),
            'results': indexRows,
          };
          changed = true;
        }
      }
      if (!changed) continue;
      DiscoveryWire.validateData(payload);
      await store.putProjection(
        kind: itemsProjectionKind,
        resourceKey: projection.resourceKey,
        schemaVersion: projection.schemaVersion,
        payload: payload,
        receivedAt: projection.receivedAt,
        sourceGeneratedAt: projection.sourceGeneratedAt,
        sourceUpdatedAt: projection.sourceUpdatedAt,
        lastVerifiedOnlineAt: projection.lastVerifiedOnlineAt,
        freshUntil: projection.freshUntil,
        expiresAt: projection.expiresAt,
        freshnessPolicyId: projection.freshnessPolicyId,
      );
    }
  }

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
    DiscoveryWire.validateData({
      'results': [Map<String, dynamic>.from(item)],
    });
    final identity = item['identity'];
    final savedFact = item['saved'];
    if (identity is! Map ||
        identity['family'] != family ||
        identity['resource'] is! Map ||
        (identity['resource'] as Map)['id'] != id ||
        savedFact is! Map ||
        savedFact['state'] != (saved ? 'saved' : 'not_saved')) {
      throw const FormatException(
        'Saved state was not confirmed for the selected possibility',
      );
    }
    await store.putProjection(
      kind: itemProjectionKind,
      resourceKey: '$family:$id',
      schemaVersion: envelope.schemaVersion,
      payload: {'item': Map<String, dynamic>.from(item)},
      sourceGeneratedAt: envelope.generatedAt,
      freshnessPolicyId: detailFreshness.id,
    );
    try {
      await _reconcileConfirmedSaved(
        family,
        id,
        Map<String, dynamic>.from(item),
      );
    } on Object {
      // The server mutation and its canonical item snapshot succeeded.
      // A stale secondary list must not turn that confirmation into a failure.
    }
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
  }) async {
    final existing = await store.readProjection(kind, resourceKey: resourceKey);
    if (existing != null && existing.receivedAt.isAfter(source.receivedAt)) {
      return;
    }
    await store.putProjection(
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
    final key = source.sourceKey;
    final inflight = _inflightOwnerRefreshes[key];
    if (inflight != null) {
      await inflight;
      return;
    }
    final request = engine.refreshSource(source);
    _inflightOwnerRefreshes[key] = request;
    try {
      await request;
    } finally {
      if (identical(_inflightOwnerRefreshes[key], request)) {
        _inflightOwnerRefreshes.remove(key);
      }
    }
  }
}
