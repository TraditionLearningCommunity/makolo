import '../../data/local/profile_store.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../sync/freshness.dart';
import 'discovery_wire.dart';

enum DiscoveryFieldState {
  noMatch,
  endOfField,
  noCurrentProposal,
  offlineWithSnapshot,
  offlineNoSnapshot,
  serverUnavailableNoSnapshot,
  contractError,
  continuationRejected,
}

class DiscoveryItemPresentation {
  const DiscoveryItemPresentation({
    required this.family,
    required this.id,
    required this.candidateKey,
    required this.title,
    required this.summary,
    required this.capabilities,
    required this.links,
    required this.savedState,
    this.occurrenceId,
    this.representationKind,
    this.routeLabel,
    this.imageUrl,
    this.eyebrow,
    this.owner,
    this.place,
    this.timing,
    this.availability,
    this.price,
    this.latitude,
    this.longitude,
    this.distanceKm,
    this.revisionId,
    this.wire = const {},
  });

  final String family;
  final String id;
  final String candidateKey;
  final String? occurrenceId;
  final String? revisionId;

  /// Complete server-owned possibility facts, without client inference.
  final Map<String, dynamic> wire;
  final String? representationKind;
  final String? routeLabel;
  final String title;
  final String summary;
  final String? imageUrl;
  final String? eyebrow;
  final String? owner;
  final String? place;
  final String? timing;
  final String? availability;
  final String? price;
  final double? latitude;
  final double? longitude;
  final double? distanceKm;
  final String savedState;
  final Set<String> capabilities;
  final Map<String, String> links;

  Map<String, dynamic>? get identity => _map(wire['identity']);
  Map<String, dynamic>? get representation => _map(wire['representation']);
  Map<String, dynamic>? get ownerFacts => _map(wire['owner']);
  Map<String, dynamic>? get provenance => _map(wire['provenance']);
  Map<String, dynamic>? get personalRelation => _map(wire['personal_relation']);
  Map<String, dynamic>? get saved => _map(wire['saved']);
  Map<String, dynamic>? get watch => _map(wire['watch']);
  Map<String, dynamic>? get priceFacts => _map(wire['price']);
  Map<String, dynamic>? get availabilityFacts => _map(wire['availability']);
  Map<String, dynamic>? get placeFacts => _map(wire['place']);
  Map<String, dynamic>? get timingFacts => _map(wire['timing']);
  Map<String, dynamic>? get engagement => _map(wire['engagement']);
  Map<String, dynamic>? get detailFacts => _map(wire['detail']);
  Map<String, dynamic>? get participantPresentation =>
      _map(wire['participant_presentation']);
  Map<String, dynamic>? get knowledge => _map(wire['knowledge']);
  Map<String, dynamic>? get freshness => _map(wire['freshness']);
  List<Map<String, dynamic>> get facts => _objectFacts(wire['facts']);
  List<Map<String, dynamic>> get assessment => _objectFacts(wire['assessment']);
  List<Map<String, dynamic>> get variants => _objectFacts(wire['variants']);
  List<Map<String, dynamic>> get relations => _objectFacts(wire['relations']);
  List<Map<String, dynamic>> get temporalFacts =>
      _objectFacts(wire['temporal_facts']);
  List<Map<String, dynamic>> get spatialFacts =>
      _objectFacts(wire['spatial_facts']);
  List<Map<String, dynamic>> get mediaBindings =>
      _objectFacts(wire['media_bindings']);
  List<Map<String, dynamic>> get presentationFacts =>
      _objectFacts(wire['presentation_facts']);
  List<Map<String, dynamic>> get handoffs => _objectFacts(wire['handoffs']);

  bool get canSave => capabilities.contains('save');
  bool get canUnsave => capabilities.contains('unsave');
  bool get isMappable {
    if (latitude != null &&
        longitude != null &&
        latitude! >= -90 &&
        latitude! <= 90 &&
        longitude! >= -180 &&
        longitude! <= 180) {
      return true;
    }
    for (final fact in spatialFacts) {
      final place = _map(fact['place']) ?? fact;
      final lat = _double(place['latitude']);
      final lon = _double(place['longitude']);
      if (lat != null &&
          lon != null &&
          lat >= -90 &&
          lat <= 90 &&
          lon >= -180 &&
          lon <= 180) {
        return true;
      }
    }
    return false;
  }
}

class DiscoveryCollectionPresentation {
  const DiscoveryCollectionPresentation({
    required this.items,
    required this.count,
    required this.page,
    required this.pageSize,
    required this.hasNext,
    this.wire = const {},
  });

  final List<DiscoveryItemPresentation> items;
  final int count;
  final int page;
  final int pageSize;
  final bool hasNext;

  /// Complete collection context, continuation, selection and terminal facts.
  final Map<String, dynamic> wire;

  Map<String, dynamic>? get envelopeMeta =>
      _map(wire[DiscoveryWire.snapshotMetaKey]);
  Map<String, dynamic>? get continuation => _map(wire['continuation']);
  Map<String, dynamic>? get selection => _map(wire['selection']);
  Map<String, dynamic>? get terminal => _map(wire['terminal']);
  Map<String, dynamic>? get exploration => _map(wire['exploration']);
  String? get continuationToken => _text(continuation?['token']);
  String? get surface => _text(wire['surface']);
  Map<String, dynamic>? get actor => _map(wire['actor']);
  Map<String, dynamic>? get viewer => _map(wire['viewer']);
  Map<String, dynamic>? get freshness => _map(wire['freshness']);
  List<Map<String, dynamic>> get handoffs => _objectFacts(wire['handoffs']);
  Set<String> get capabilities => Set.unmodifiable(
    (wire['capabilities'] is List ? wire['capabilities'] as List : const [])
        .whereType<String>(),
  );
  String? get selectionReason => _text(selection?['reason']);
  String? get terminalState => _text(terminal?['state']);
  String? get continuationState => _text(continuation?['state']);
  bool get hasPrevious => wire['has_previous'] == true;
  String? get timezone => _text(wire['timezone']);
  bool get nearbyActive => wire['nearby_active'] == true;

  /// Reconcile an authoritative next server lot by canonical candidate key.
  ///
  /// Existing order is stable; newer facts replace the matching observation
  /// in place. New candidates follow in server order. The arriving page owns
  /// the continuation and terminal context.
  DiscoveryCollectionPresentation reconcile(
    DiscoveryCollectionPresentation incoming,
  ) {
    if (incoming.page <= 1) return incoming;
    if (incoming.page != page + 1) {
      throw const FormatException('Non-contiguous Discovery continuation');
    }
    final ordered = <DiscoveryItemPresentation>[];
    final positions = <String, int>{};
    for (final item in [...items, ...incoming.items]) {
      final index = positions[item.candidateKey];
      if (index == null) {
        positions[item.candidateKey] = ordered.length;
        ordered.add(item);
      } else {
        ordered[index] = item;
      }
    }
    final reconciledRows = List<Map<String, dynamic>>.unmodifiable(
      ordered.map((item) => item.wire),
    );
    return DiscoveryCollectionPresentation(
      items: List.unmodifiable(ordered),
      count: incoming.count,
      page: incoming.page,
      pageSize: incoming.pageSize,
      hasNext: incoming.hasNext,
      wire: Map.unmodifiable({
        ...incoming.wire,
        'results': reconciledRows,
        'items': reconciledRows,
      }),
    );
  }

  static const empty = DiscoveryCollectionPresentation(
    items: [],
    count: 0,
    page: 1,
    pageSize: 24,
    hasNext: false,
  );
}

class DiscoveryFieldSelection {
  const DiscoveryFieldSelection({
    required this.collection,
    required this.surface,
    required this.states,
  });

  final DiscoveryCollectionPresentation collection;
  final MakoloSurfacePresentation surface;
  final Set<DiscoveryFieldState> states;

  bool get hasSnapshot =>
      !states.contains(DiscoveryFieldState.offlineNoSnapshot) &&
      !states.contains(DiscoveryFieldState.serverUnavailableNoSnapshot);
  bool get reachedEnd => states.contains(DiscoveryFieldState.endOfField);
}

class DiscoveryMapPoint {
  const DiscoveryMapPoint({
    required this.activityId,
    required this.occurrenceId,
    required this.title,
    required this.latitude,
    required this.longitude,
    this.candidateKey,
    this.locality,
    this.placeName,
  });

  final String activityId;
  final String occurrenceId;
  final String title;
  final double latitude;
  final double longitude;
  final String? candidateKey;
  final String? locality;
  final String? placeName;
}

/// Exact spatial observations of one canonical possibility.
/// A locality without coordinates remains in the general Discovery field.
class DiscoverySpatialAnchor {
  const DiscoverySpatialAnchor({
    required this.candidateKey,
    required this.latitude,
    required this.longitude,
    required this.fact,
  });

  final String candidateKey;
  final double latitude;
  final double longitude;
  final Map<String, dynamic> fact;
}

class DiscoverySelector {
  const DiscoverySelector();

  DiscoveryFieldSelection select({
    required StoredProjection? projection,
    required bool hasCriteria,
    FreshnessState freshness = FreshnessState.fresh,
    MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
    MakoloFailureCue failure = MakoloFailureCue.none,
    bool refreshing = false,
    bool serverUnavailable = false,
    String? sourceErrorCode,
    DateTime? now,
  }) {
    if (projection == null) {
      final states = <DiscoveryFieldState>{
        if (sourceErrorCode == 'contract_error')
          DiscoveryFieldState.contractError,
        if (sourceErrorCode == 'continuation_rejected')
          DiscoveryFieldState.continuationRejected,
        if (reachability == MakoloReachabilityCue.temporarilyUnavailable)
          serverUnavailable
              ? DiscoveryFieldState.serverUnavailableNoSnapshot
              : DiscoveryFieldState.offlineNoSnapshot,
      };
      return DiscoveryFieldSelection(
        collection: DiscoveryCollectionPresentation.empty,
        surface: MakoloSurfacePresentation(
          availability: states.isEmpty
              ? MakoloAvailabilityCue.initial
              : MakoloAvailabilityCue.empty,
          reachability: reachability,
          failure: sourceErrorCode == 'contract_error'
              ? MakoloFailureCue.blocking
              : failure,
          refreshing: refreshing,
        ),
        states: Set.unmodifiable(states),
      );
    }

    final rawItems =
        projection.payload['results'] ?? projection.payload['items'];
    try {
      if (projection.kind != 'discovery.items' ||
          projection.schemaVersion != 1) {
        throw const FormatException('Incompatible Discovery snapshot');
      }
      DiscoveryWire.validateData(projection.payload);
    } on FormatException {
      return DiscoveryFieldSelection(
        collection: DiscoveryCollectionPresentation.empty,
        surface: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.empty,
          freshness: _freshnessCue(freshness),
          reachability: reachability,
          failure: MakoloFailureCue.blocking,
          refreshing: refreshing,
        ),
        states: const {DiscoveryFieldState.contractError},
      );
    }

    final collection = _collectionFromPayload(
      projection.payload,
      now: now ?? DateTime.now(),
    );
    final malformedOnly = rawItems.isNotEmpty && collection.items.isEmpty;
    final states = <DiscoveryFieldState>{
      if (sourceErrorCode == 'contract_error')
        DiscoveryFieldState.contractError,
      if (sourceErrorCode == 'continuation_rejected')
        DiscoveryFieldState.continuationRejected,
    };

    if (reachability == MakoloReachabilityCue.temporarilyUnavailable) {
      states.add(DiscoveryFieldState.offlineWithSnapshot);
    }
    final selection = collection.selection;
    final terminal = collection.terminal;
    final reason = _text(selection?['reason']);
    if (reason == 'no_match') {
      states.add(DiscoveryFieldState.noMatch);
    } else if (reason == 'no_current_proposal') {
      states.add(DiscoveryFieldState.noCurrentProposal);
    } else if (selection == null && collection.items.isEmpty) {
      states.add(
        hasCriteria
            ? DiscoveryFieldState.noMatch
            : DiscoveryFieldState.noCurrentProposal,
      );
    }
    if (terminal?['state'] == 'end_of_field' ||
        (collection.continuationState == 'end' &&
            collection.items.isNotEmpty &&
            selection?['state'] == 'ready') ||
        (terminal == null &&
            collection.items.isNotEmpty &&
            !collection.hasNext)) {
      states.add(DiscoveryFieldState.endOfField);
    }

    return DiscoveryFieldSelection(
      collection: collection,
      surface: MakoloSurfacePresentation(
        availability: collection.items.isEmpty
            ? MakoloAvailabilityCue.empty
            : MakoloAvailabilityCue.content,
        freshness: _freshnessCue(freshness),
        reachability: reachability,
        failure: malformedOnly ? MakoloFailureCue.blocking : failure,
        refreshing: refreshing,
      ),
      states: Set.unmodifiable(states),
    );
  }

  /// The same canonical projection parser can be used by unauthenticated
  /// clients without creating a local Profile database or a second selector.
  DiscoveryCollectionPresentation publicCollection(
    Map<String, dynamic> payload, {
    DateTime? now,
  }) => _collectionFromPayload(payload, now: now ?? DateTime.now());

  /// Parse a public item detail using the same Presentation contract.
  DiscoveryItemPresentation? publicItem(
    Map<String, dynamic> item, {
    DateTime? now,
  }) {
    DiscoveryWire.validateData({
      'results': [item],
    });
    return _item(item, now: now ?? DateTime.now());
  }

  DiscoveryCollectionPresentation collection(
    StoredProjection? projection, {
    DateTime? now,
  }) {
    final payload = projection?.payload;
    if (payload == null) return DiscoveryCollectionPresentation.empty;
    if (projection!.kind != 'discovery.items' ||
        projection.schemaVersion != 1) {
      throw const FormatException('Incompatible Discovery snapshot');
    }
    return _collectionFromPayload(payload, now: now ?? DateTime.now());
  }

  DiscoveryCollectionPresentation _collectionFromPayload(
    Map<String, dynamic> payload, {
    required DateTime now,
  }) {
    final rawItems = payload['results'] ?? payload['items'];
    DiscoveryWire.validateData(payload);
    final items = rawItems is List
        ? rawItems
              .whereType<Map>()
              .map((item) => _item(Map<String, dynamic>.from(item), now: now))
              .whereType<DiscoveryItemPresentation>()
              .toList(growable: false)
        : const <DiscoveryItemPresentation>[];
    return DiscoveryCollectionPresentation(
      items: items,
      count: _int(payload['count']) ?? items.length,
      page: _int(payload['page']) ?? 1,
      pageSize: _int(payload['page_size']) ?? items.length,
      hasNext: payload['has_next'] == true,
      wire: Map.unmodifiable(payload),
    );
  }

  DiscoveryItemPresentation? detail(
    StoredProjection? projection, {
    DateTime? now,
  }) {
    if (projection != null &&
        (projection.kind != 'discovery.item' ||
            projection.schemaVersion != 1)) {
      throw const FormatException('Incompatible Discovery detail snapshot');
    }
    final raw = projection?.payload['item'];
    if (raw is! Map) return null;
    final item = Map<String, dynamic>.from(raw);
    DiscoveryWire.validateData({
      'results': [item],
    });
    return _item(item, now: now ?? DateTime.now());
  }

  /// Multiple spatial facts may point to distinct real places. Neither
  /// missing coordinates nor a place name is converted into an invented pin.
  List<DiscoverySpatialAnchor> spatialAnchorsFromCollection(
    DiscoveryCollectionPresentation collection,
  ) {
    final anchors = <DiscoverySpatialAnchor>[];
    for (final item in collection.items) {
      final facts = <Map<String, dynamic>>[...item.spatialFacts];
      final legacyPlace = item.placeFacts;
      if (legacyPlace != null) {
        final lat = _double(legacyPlace['latitude']);
        final lon = _double(legacyPlace['longitude']);
        final alreadyLocated = facts.any((fact) {
          final place = _map(fact['place']) ?? fact;
          return _double(place['latitude']) == lat &&
              _double(place['longitude']) == lon;
        });
        if (!alreadyLocated) facts.add(legacyPlace);
      }
      for (final fact in facts) {
        final place = _map(fact['place']) ?? fact;
        final latitude = _double(place['latitude']);
        final longitude = _double(place['longitude']);
        if (latitude == null ||
            longitude == null ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180) {
          continue;
        }
        anchors.add(
          DiscoverySpatialAnchor(
            candidateKey: item.candidateKey,
            latitude: latitude,
            longitude: longitude,
            fact: Map.unmodifiable(fact),
          ),
        );
      }
    }
    return List.unmodifiable(anchors);
  }

  List<DiscoveryMapPoint> mapPointsFromCollection(
    DiscoveryCollectionPresentation collection,
  ) {
    final points = <DiscoveryMapPoint>[];
    for (final item in collection.items) {
      if (!item.isMappable || item.occurrenceId == null) continue;
      points.add(
        DiscoveryMapPoint(
          activityId: item.id,
          occurrenceId: item.occurrenceId!,
          candidateKey: item.candidateKey,
          title: item.title,
          latitude: item.latitude!,
          longitude: item.longitude!,
          placeName: item.place,
        ),
      );
    }
    return List.unmodifiable(points);
  }

  /// Compatibility parser for the existing `discovery.map` snapshot.
  ///
  /// G05 does not use this as a second field of truth; production spatial
  /// composition derives from [mapPointsFromCollection].
  List<DiscoveryMapPoint> mapPoints(StoredProjection? projection) {
    final results = projection?.payload['results'];
    if (results is! List) return const [];
    final points = <DiscoveryMapPoint>[];
    for (final raw in results.whereType<Map>()) {
      final item = Map<String, dynamic>.from(raw);
      final place = _map(item['place']);
      final lat = _double(place?['latitude']);
      final lon = _double(place?['longitude']);
      final activityId = _text(item['activity_id']);
      final occurrenceId = _text(item['occurrence_id']);
      final title = _text(item['title']);
      if (lat == null ||
          lon == null ||
          activityId == null ||
          occurrenceId == null ||
          title == null) {
        continue;
      }
      points.add(
        DiscoveryMapPoint(
          activityId: activityId,
          occurrenceId: occurrenceId,
          title: title,
          latitude: lat,
          longitude: lon,
          locality: _text(place?['locality']),
          placeName: _text(place?['name']),
        ),
      );
    }
    return List.unmodifiable(points);
  }

  DiscoveryItemPresentation? _item(
    Map<String, dynamic> item, {
    required DateTime now,
  }) {
    final identity = _map(item['identity']);
    final resource = _map(identity?['resource']);
    final representation = _map(item['representation']);
    final family = _text(identity?['family']);
    final id = _text(resource?['id']);
    final candidateKey = _text(identity?['candidate_key']);
    final title = _text(representation?['title']);
    if (family == null || id == null || candidateKey == null || title == null) {
      return null;
    }

    final occurrence = _map(identity?['occurrence']);
    final owner = _map(item['owner']);
    final place = _map(item['place']);
    final timing = _map(item['timing']);
    final availability = _map(item['availability']);
    final price = _map(item['price']);
    final saved = _map(item['saved']);
    final capabilities = item['capabilities'] is List
        ? (item['capabilities'] as List).whereType<String>().toSet()
        : <String>{};
    final links = <String, String>{};
    final rawLinks = _map(item['links']);
    if (rawLinks != null) {
      for (final entry in rawLinks.entries) {
        if (entry.value is String && (entry.value as String).isNotEmpty) {
          links[entry.key] = entry.value as String;
        }
      }
    }

    final placeParts = <String>[];
    final placeName = _text(place?['name']);
    final locality = _text(place?['locality']);
    if (placeName != null) placeParts.add(placeName);
    if (locality != null && locality != placeName) placeParts.add(locality);
    final timingText = _humanTiming(timing, now: now);

    String? priceText;
    final priceState = _text(price?['state']);
    if (priceState == 'free') {
      priceText = 'Gratuit';
    } else {
      final minimum = _text(price?['minimum']);
      final maximum = _text(price?['maximum']);
      final currency = _text(price?['currency']);
      if (minimum != null) {
        final amount =
            priceState == 'range' && maximum != null && maximum != minimum
            ? '$minimum – $maximum'
            : priceState == 'priced' || priceState == 'variant_dependent'
            ? 'À partir de $minimum'
            : minimum;
        priceText = currency == null ? amount : '$amount $currency';
      }
    }

    return DiscoveryItemPresentation(
      family: family,
      id: id,
      candidateKey: candidateKey,
      occurrenceId: _text(occurrence?['id']),
      revisionId: _text(_map(identity?['revision'])?['id']),
      wire: Map.unmodifiable(item),
      representationKind: _text(representation?['kind']),
      routeLabel: _text(representation?['route_label']),
      title: title,
      summary: _text(representation?['summary']) ?? '',
      imageUrl: _text(representation?['image_url']),
      eyebrow: _text(representation?['eyebrow']),
      owner: _text(owner?['display_name']),
      place: placeParts.isEmpty ? null : placeParts.join(' · '),
      timing: timingText,
      availability: MakoloHumanization.humanStatus(
        _text(availability?['state']),
      ),
      price: priceText,
      latitude: _double(place?['latitude']),
      longitude: _double(place?['longitude']),
      distanceKm: _double(place?['distance_km']),
      savedState: _text(saved?['state']) ?? 'unknown',
      capabilities: Set.unmodifiable(capabilities),
      links: Map.unmodifiable(links),
    );
  }

  MakoloFreshnessCue _freshnessCue(FreshnessState state) {
    return switch (state) {
      FreshnessState.fresh => MakoloFreshnessCue.current,
      FreshnessState.usableButOld => MakoloFreshnessCue.oldObservation,
      FreshnessState.refreshRecommended =>
        MakoloFreshnessCue.refreshRecommended,
      FreshnessState.revalidationRequired =>
        MakoloFreshnessCue.revalidationRequired,
      FreshnessState.expired => MakoloFreshnessCue.expired,
    };
  }
}

List<Map<String, dynamic>> _objectFacts(Object? raw) {
  if (raw is! List) return const [];
  return List.unmodifiable(
    raw.whereType<Map>().map(
      (value) =>
          Map<String, dynamic>.unmodifiable(Map<String, dynamic>.from(value)),
    ),
  );
}

Map<String, dynamic>? _map(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : null;

String? _text(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

int? _int(Object? value) => value is int ? value : int.tryParse('$value');

double? _double(Object? value) =>
    value is num ? value.toDouble() : double.tryParse('$value');

String? _humanTiming(Map<String, dynamic>? timing, {required DateTime now}) {
  if (timing == null) return null;
  final instant = MakoloHumanization.tryParseInstant(timing['start_at']);
  if (instant != null) {
    return MakoloHumanization.formatDateTime(instant, now: now);
  }

  final date = _text(timing['start_date']);
  final time = _text(timing['start_time']);
  final parsed = date == null
      ? null
      : DateTime.tryParse(time == null ? date : '${date}T$time');
  if (parsed != null) {
    return time == null
        ? MakoloHumanization.formatDay(parsed, now: now)
        : MakoloHumanization.formatDateTime(parsed, now: now);
  }
  return null;
}
