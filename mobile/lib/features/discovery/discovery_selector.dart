import '../../data/local/profile_store.dart';

class DiscoveryItemPresentation {
  const DiscoveryItemPresentation({
    required this.family,
    required this.id,
    required this.title,
    required this.summary,
    required this.capabilities,
    required this.links,
    required this.savedState,
    this.occurrenceId,
    this.imageUrl,
    this.eyebrow,
    this.owner,
    this.place,
    this.timing,
    this.availability,
    this.price,
  });

  final String family;
  final String id;
  final String? occurrenceId;
  final String title;
  final String summary;
  final String? imageUrl;
  final String? eyebrow;
  final String? owner;
  final String? place;
  final String? timing;
  final String? availability;
  final String? price;
  final String savedState;
  final Set<String> capabilities;
  final Map<String, String> links;

  bool get canSave => capabilities.contains('save');
  bool get canUnsave => capabilities.contains('unsave');
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

class DiscoveryMapPoint {
  const DiscoveryMapPoint({
    required this.activityId,
    required this.occurrenceId,
    required this.title,
    required this.latitude,
    required this.longitude,
    this.locality,
    this.placeName,
  });

  final String activityId;
  final String occurrenceId;
  final String title;
  final double latitude;
  final double longitude;
  final String? locality;
  final String? placeName;
}

class DiscoverySelector {
  const DiscoverySelector();

  DiscoveryCollectionPresentation collection(StoredProjection? projection) {
    final payload = projection?.payload;
    if (payload == null) return DiscoveryCollectionPresentation.empty;
    final rawItems = payload['results'];
    final items = rawItems is List
        ? rawItems
              .whereType<Map>()
              .map((item) => _item(Map<String, dynamic>.from(item)))
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

  DiscoveryItemPresentation? detail(StoredProjection? projection) {
    final raw = projection?.payload['item'];
    if (raw is! Map) return null;
    return _item(Map<String, dynamic>.from(raw));
  }

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

  DiscoveryItemPresentation? _item(Map<String, dynamic> item) {
    final identity = _map(item['identity']);
    final resource = _map(identity?['resource']);
    final representation = _map(item['representation']);
    final family = _text(identity?['family']);
    final id = _text(resource?['id']);
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
        ? (item['capabilities'] as List)
              .whereType<String>()
              .toSet()
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
    if (locality != null) placeParts.add(locality);
    final timingText =
        _text(timing?['start_at']) ??
        [
          _text(timing?['start_date']),
          _text(timing?['start_time']),
        ].whereType<String>().join(' ');

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
      occurrenceId: _text(occurrence?['id']),
      title: title,
      summary: _text(representation?['summary']) ?? '',
      imageUrl: _text(representation?['image_url']),
      eyebrow: _text(representation?['eyebrow']),
      owner: _text(owner?['display_name']),
      place: placeParts.isEmpty ? null : placeParts.join(' · '),
      timing: timingText?.trim().isEmpty == true ? null : timingText,
      availability: _text(availability?['state']),
      price: priceText,
      savedState: _text(saved?['state']) ?? 'unknown',
      capabilities: Set.unmodifiable(capabilities),
      links: Map.unmodifiable(links),
    );
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
