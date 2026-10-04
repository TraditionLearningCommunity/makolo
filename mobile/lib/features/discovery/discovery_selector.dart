import '../../data/local/profile_store.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../sync/freshness.dart';

enum DiscoveryFieldState {
  noMatch,
  endOfField,
  noCurrentProposal,
  offlineWithSnapshot,
  offlineNoSnapshot,
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
  });

  final String family;
  final String id;
  final String candidateKey;
  final String? occurrenceId;
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

  bool get canSave => capabilities.contains('save');
  bool get canUnsave => capabilities.contains('unsave');
  bool get isMappable => latitude != null && longitude != null;
}

class DiscoveryCollectionPresentation {
  const DiscoveryCollectionPresentation({
    required this.items,
    required this.count,
    required this.page,
    required this.pageSize,
    required this.hasNext,
  });

  final List<DiscoveryItemPresentation> items;
  final int count;
  final int page;
  final int pageSize;
  final bool hasNext;

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
      !states.contains(DiscoveryFieldState.offlineNoSnapshot);
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

class DiscoverySelector {
  const DiscoverySelector();

  DiscoveryFieldSelection select({
    required StoredProjection? projection,
    required bool hasCriteria,
    FreshnessState freshness = FreshnessState.fresh,
    MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
    MakoloFailureCue failure = MakoloFailureCue.none,
    bool refreshing = false,
    DateTime? now,
  }) {
    if (projection == null) {
      final states = <DiscoveryFieldState>{
        if (reachability == MakoloReachabilityCue.temporarilyUnavailable)
          DiscoveryFieldState.offlineNoSnapshot,
      };
      return DiscoveryFieldSelection(
        collection: DiscoveryCollectionPresentation.empty,
        surface: MakoloSurfacePresentation(
          availability: states.isEmpty
              ? MakoloAvailabilityCue.initial
              : MakoloAvailabilityCue.empty,
          reachability: reachability,
          failure: failure,
          refreshing: refreshing,
        ),
        states: Set.unmodifiable(states),
      );
    }

    final rawItems = projection.payload['results'];
    if (rawItems is! List) {
      return DiscoveryFieldSelection(
        collection: DiscoveryCollectionPresentation.empty,
        surface: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.empty,
          freshness: _freshnessCue(freshness),
          reachability: reachability,
          failure: MakoloFailureCue.blocking,
          refreshing: refreshing,
        ),
        states: const {},
      );
    }

    final collection = _collectionFromPayload(
      projection.payload,
      now: now ?? DateTime.now(),
    );
    final malformedOnly = rawItems.isNotEmpty && collection.items.isEmpty;
    final states = <DiscoveryFieldState>{};

    if (reachability == MakoloReachabilityCue.temporarilyUnavailable) {
      states.add(DiscoveryFieldState.offlineWithSnapshot);
    }
    if (collection.items.isEmpty) {
      states.add(
        hasCriteria
            ? DiscoveryFieldState.noMatch
            : DiscoveryFieldState.noCurrentProposal,
      );
    } else if (!collection.hasNext) {
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

  DiscoveryCollectionPresentation collection(
    StoredProjection? projection, {
    DateTime? now,
  }) {
    final payload = projection?.payload;
    if (payload == null) return DiscoveryCollectionPresentation.empty;
    return _collectionFromPayload(payload, now: now ?? DateTime.now());
  }

  DiscoveryCollectionPresentation _collectionFromPayload(
    Map<String, dynamic> payload, {
    required DateTime now,
  }) {
    final rawItems = payload['results'];
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
    );
  }

  DiscoveryItemPresentation? detail(
    StoredProjection? projection, {
    DateTime? now,
  }) {
    final raw = projection?.payload['item'];
    if (raw is! Map) return null;
    return _item(Map<String, dynamic>.from(raw), now: now ?? DateTime.now());
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
    final candidateKey = _text(identity?['candidate_key']) ?? '$family:$id';
    final title = _text(representation?['title']);
    if (family == null || id == null || title == null) return null;

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
      final currency = _text(price?['currency']);
      if (minimum != null) {
        priceText = currency == null ? minimum : '$minimum $currency';
      }
    }

    return DiscoveryItemPresentation(
      family: family,
      id: id,
      candidateKey: candidateKey,
      occurrenceId: _text(occurrence?['id']),
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
