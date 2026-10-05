import '../../data/local/profile_store.dart';
import '../../presentation/humanization.dart';

class ActivityOccurrenceSummary {
  const ActivityOccurrenceSummary({
    required this.id,
    required this.label,
    required this.state,
    this.timing,
  });

  final String id;
  final String label;
  final String? state;
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
  final String? state;
  final String? availability;
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
  final String? state;
  final String? availability;
  final String? timing;
  final String? place;
  final Set<String> capabilities;

  bool get canOpenDayOf => capabilities.contains('open_day_of');
}

class DiscoveryDetailSelector {
  const DiscoveryDetailSelector();

  ActivityDetailPresentation? activity(
    StoredProjection? projection, {
    DateTime? now,
  }) {
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
            state: MakoloHumanization.humanStatus(_text(row['state'])),
            timing: _timing(_map(row['timing']), now: now ?? DateTime.now()),
          ),
        );
      }
    }
    return ActivityDetailPresentation(
      title: title,
      summary: _text(representation?['summary']) ?? '',
      state: MakoloHumanization.humanStatus(_text(state?['code'])),
      availability: MakoloHumanization.humanStatus(
        _text(availability?['state']),
      ),
      owner: _text(owner?['display_name']),
      vertical: _text(identity?['vertical']),
      occurrences: List.unmodifiable(items),
    );
  }

  ActivityDetailPresentation? activityPreview(
    StoredProjection? projection, {
    DateTime? now,
  }) {
    final item = _map(projection?.payload['item']);
    if (item == null) return null;
    final identity = _map(item['identity']);
    final representation = _map(item['representation']);
    final owner = _map(item['owner']);
    final availability = _map(item['availability']);
    final occurrence = _map(identity?['occurrence']);
    final title = _text(representation?['title']);
    if (title == null) return null;

    final occurrenceId = _text(occurrence?['id']);
    final occurrences = occurrenceId == null
        ? const <ActivityOccurrenceSummary>[]
        : <ActivityOccurrenceSummary>[
            ActivityOccurrenceSummary(
              id: occurrenceId,
              label: title,
              state: null,
              timing: _timing(_map(item['timing']), now: now ?? DateTime.now()),
            ),
          ];

    return ActivityDetailPresentation(
      title: title,
      summary: _text(representation?['summary']) ?? '',
      state: null,
      availability: MakoloHumanization.humanStatus(
        _text(availability?['state']),
      ),
      owner: _text(owner?['display_name']),
      vertical:
          _text(representation?['eyebrow']) ??
          _text(representation?['route_label']),
      occurrences: List.unmodifiable(occurrences),
    );
  }

  OccurrenceDetailPresentation? occurrence(
    StoredProjection? projection, {
    DateTime? now,
  }) {
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
      state: MakoloHumanization.humanStatus(_text(state?['code'])),
      availability: MakoloHumanization.humanStatus(
        _text(availability?['state']),
      ),
      timing: _timing(_map(payload['timing']), now: now ?? DateTime.now()),
      place: placeParts.isEmpty ? null : placeParts.join(' · '),
      capabilities: Set.unmodifiable(capabilities),
    );
  }
  OccurrenceDetailPresentation? occurrencePreview(
    StoredProjection? projection, {
    DateTime? now,
  }) {
    final payload = projection?.payload;
    if (payload == null) return null;

    final item = _map(payload['item']);
    if (item != null) {
      final identity = _map(item['identity']);
      final resource = _map(identity?['resource']);
      final representation = _map(item['representation']);
      final availability = _map(item['availability']);
      final activityId = _text(resource?['id']);
      final activityTitle = _text(representation?['title']);
      if (activityId == null || activityTitle == null) return null;
      return OccurrenceDetailPresentation(
        activityId: activityId,
        activityTitle: activityTitle,
        state: null,
        availability: MakoloHumanization.humanStatus(
          _text(availability?['state']),
        ),
        timing: _timing(_map(item['timing']), now: now ?? DateTime.now()),
        place: _placeLabel(_map(item['place'])),
        capabilities: const {},
      );
    }

    final activity = _map(payload['activity']);
    final occurrence = _map(payload['occurrence']);
    final availability = _map(payload['availability']);
    final activityId = _text(activity?['id']);
    final activityTitle = _text(activity?['title']);
    if (activityId == null || activityTitle == null || occurrence == null) {
      return null;
    }
    return OccurrenceDetailPresentation(
      activityId: activityId,
      activityTitle: activityTitle,
      state: MakoloHumanization.humanStatus(_text(occurrence['state'])),
      availability: MakoloHumanization.humanStatus(
        _text(availability?['state']),
      ),
      timing: _timing(_map(occurrence['timing']), now: now ?? DateTime.now()),
      place: _placeLabel(_map(occurrence['place'])),
      capabilities: const {},
    );
  }
}

String? _timing(Map<String, dynamic>? timing, {required DateTime now}) {
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
  if (parsed == null) return null;
  return time == null
      ? MakoloHumanization.formatDay(parsed, now: now)
      : MakoloHumanization.formatDateTime(parsed, now: now);
}

Map<String, dynamic>? _map(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : null;

String? _text(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;

}

String? _placeLabel(Map<String, dynamic>? place) {
  if (place == null) return null;
  final parts = <String>[];
  final name = _text(place['name']);
  final locality = _text(place['locality']);
  if (name != null) parts.add(name);
  if (locality != null && locality != name) parts.add(locality);
  return parts.isEmpty ? null : parts.join(' · ');
}
