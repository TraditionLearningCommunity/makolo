import '../../data/local/profile_store.dart';

class ActivityOccurrenceSummary {
  const ActivityOccurrenceSummary({
    required this.id,
    required this.label,
    required this.state,
    this.timing,
  });

  final String id;
  final String label;
  final String state;
  final String? timing;
}

class ActivityDetailPresentation {
  const ActivityDetailPresentation({
    required this.title,
    required this.summary,
    required this.state,
    required this.availability,
    required this.occurrences,
    this.owner,
    this.vertical,
  });

  final String title;
  final String summary;
  final String state;
  final String availability;
  final String? owner;
  final String? vertical;
  final List<ActivityOccurrenceSummary> occurrences;
}

class OccurrenceDetailPresentation {
  const OccurrenceDetailPresentation({
    required this.activityId,
    required this.activityTitle,
    required this.state,
    required this.availability,
    required this.capabilities,
    this.timing,
    this.place,
  });

  final String activityId;
  final String activityTitle;
  final String state;
  final String availability;
  final String? timing;
  final String? place;
  final Set<String> capabilities;

  bool get canOpenDayOf => capabilities.contains('open_day_of');
}

class DiscoveryDetailSelector {
  const DiscoveryDetailSelector();

  ActivityDetailPresentation? activity(StoredProjection? projection) {
    final payload = projection?.payload;
    if (payload == null) return null;
    final representation = _map(payload['representation']);
    final state = _map(payload['state']);
    final availability = _map(payload['availability']);
    final owner = _map(payload['owner']);
    final identity = _map(payload['identity']);
    final occurrences = payload['occurrences'];
    final title = _text(representation?['title']);
    if (title == null) return null;
    final items = <ActivityOccurrenceSummary>[];
    if (occurrences is List) {
      for (final raw in occurrences.whereType<Map>()) {
        final row = Map<String, dynamic>.from(raw);
        final id = _text(row['id']);
        if (id == null) continue;
        items.add(
          ActivityOccurrenceSummary(
            id: id,
            label: _text(row['label']) ?? 'Réalisation',
            state: _text(row['state']) ?? 'unknown',
            timing: _timing(_map(row['timing'])),
          ),
        );
      }
    }
    return ActivityDetailPresentation(
      title: title,
      summary: _text(representation?['summary']) ?? '',
      state: _text(state?['code']) ?? 'unknown',
      availability: _text(availability?['state']) ?? 'unknown',
      owner: _text(owner?['display_name']),
      vertical: _text(identity?['vertical']),
      occurrences: List.unmodifiable(items),
    );
  }

  OccurrenceDetailPresentation? occurrence(StoredProjection? projection) {
    final payload = projection?.payload;
    if (payload == null) return null;
    final activity = _map(payload['activity']);
    final state = _map(payload['state']);
    final availability = _map(payload['availability']);
    final place = _map(payload['place']);
    final id = _text(activity?['id']);
    final title = _text(activity?['title']);
    if (id == null || title == null) return null;
    final placeParts = <String>[];
    final name = _text(place?['name']);
    final locality = _text(place?['locality']);
    if (name != null) placeParts.add(name);
    if (locality != null) placeParts.add(locality);
    final capabilities = payload['capabilities'] is List
        ? (payload['capabilities'] as List).whereType<String>().toSet()
        : <String>{};
    return OccurrenceDetailPresentation(
      activityId: id,
      activityTitle: title,
      state: _text(state?['code']) ?? 'unknown',
      availability: _text(availability?['state']) ?? 'unknown',
      timing: _timing(_map(payload['timing'])),
      place: placeParts.isEmpty ? null : placeParts.join(' · '),
      capabilities: Set.unmodifiable(capabilities),
    );
  }
}

String? _timing(Map<String, dynamic>? timing) {
  if (timing == null) return null;
  final exact = _text(timing['start_at']);
  if (exact != null) return exact;
  final date = _text(timing['start_date']);
  final time = _text(timing['start_time']);
  return [date, time].whereType<String>().join(' ').trim().isEmpty
      ? null
      : [date, time].whereType<String>().join(' ');
}

Map<String, dynamic>? _map(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : null;

String? _text(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}
