import '../../data/local/profile_store.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import 'access_repository.dart';

class DayOfHandoff {
  const DayOfHandoff({required this.occurrenceId, required this.path});

  final String occurrenceId;
  final String path;
}

class AccessDetailPresentation {
  const AccessDetailPresentation({
    required this.available,
    required this.activityTitle,
    required this.relationship,
    required this.singleUse,
    required this.capabilities,
    required this.freshness,
    required this.sourceInvalidated,
    this.knownOnly = false,
    this.occurrenceStartsAt,
    this.occurrenceStartDate,
    this.placeName,
    this.placeAddress,
    this.accessInstructions,
    this.holderName,
    this.state,
    this.validFrom,
    this.validUntil,
    this.journeyId,
    this.dayOf,
  });

  final bool available;
  final String activityTitle;
  final String relationship;
  final bool singleUse;
  final String? state;
  final DateTime? validFrom;
  final DateTime? validUntil;
  final String? journeyId;
  final DayOfHandoff? dayOf;
  final Set<String> capabilities;
  final FreshnessState? freshness;
  final bool sourceInvalidated;
  final bool knownOnly;
  final DateTime? occurrenceStartsAt;
  final String? occurrenceStartDate;
  final String? placeName;
  final String? placeAddress;
  final String? accessInstructions;
  final String? holderName;

  bool get isBeneficiary => relationship == 'beneficiary';

  bool get canOpenDayOf =>
      isBeneficiary && capabilities.contains('open_day_of') && dayOf != null;
}

class AccessDetailSelector {
  const AccessDetailSelector();

  /// Owner-provided list facts only. A local list row is not proof of a
  /// presently valid credential, a Day-of permission, or an AccessUse.
  AccessDetailPresentation? knownFromCollection({
    required Iterable<StoredProjection> pages,
    required String accessId,
    required DateTime now,
  }) {
    for (final page in pages) {
      if (page.kind != AccessRepository.collectionProjectionKind ||
          page.schemaVersion != 1 ||
          !(page.resourceKey.startsWith('beneficiary:') ||
              page.resourceKey.startsWith('purchased_for_other:'))) {
        continue;
      }
      final rows = page.payload['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final item = _map(raw);
        if (_string(_map(item['identity'])['id']) != accessId) continue;
        final activity = _map(item['activity']);
        final occurrence = _map(item['occurrence']);
        final timing = _map(occurrence['timing']);
        final place = _map(occurrence['place']);
        final validity = _map(item['validity']);
        final state = _map(item['state']);
        final holder = _map(item['holder']);
        return AccessDetailPresentation(
          available: true,
          activityTitle: _string(activity['title']) ?? 'Accès',
          relationship: _string(item['relationship']) ?? '',
          singleUse: false,
          capabilities: const {},
          freshness: AccessRepository.freshnessPolicy.evaluate(page, now: now),
          sourceInvalidated: false,
          knownOnly: true,
          state: _string(state['label']) ?? _string(state['code']),
          validFrom: _dateTime(validity['from']),
          validUntil: _dateTime(validity['until']),
          occurrenceStartsAt: _dateTime(timing['start_at']),
          occurrenceStartDate: _string(timing['start_date']),
          placeName: _string(place['name']) ?? _string(place['locality']),
          placeAddress: _string(place['address_line']),
          accessInstructions: _string(place['access_instructions']),
          holderName: _string(holder['display_name']),
        );
      }
    }
    return null;
  }

  AccessDetailPresentation select({
    required StoredProjection? projection,
    required AccessSourceState source,
    required DateTime now,
  }) {
    if (projection == null) {
      return AccessDetailPresentation(
        available: false,
        activityTitle: '',
        relationship: '',
        singleUse: false,
        capabilities: const {},
        freshness: null,
        sourceInvalidated: source.invalidated,
      );
    }

    final base = const ProjectionSelector().select(
      projection: projection,
      freshnessPolicy: AccessRepository.freshnessPolicy,
      now: now,
      sourceInvalidated: source.invalidated,
    );
    final payload = base.payload ?? const <String, dynamic>{};
    final right = _map(payload['right']);
    final holder = _map(payload['holder']);
    final activity = _map(payload['activity']);
    final occurrence = _map(payload['occurrence']);
    final timing = _map(occurrence['timing']);
    final place = _map(occurrence['place']);
    final journey = _map(payload['journey']);
    final links = _map(payload['links']);
    final capabilities = _strings(payload['capabilities']).toSet();

    DayOfHandoff? dayOf;
    final occurrenceId = _string(occurrence['id']);
    final dayOfPath = _string(links['day_of']);
    if (capabilities.contains('open_day_of') &&
        occurrenceId != null &&
        dayOfPath != null) {
      dayOf = DayOfHandoff(occurrenceId: occurrenceId, path: dayOfPath);
    }

    return AccessDetailPresentation(
      available: true,
      activityTitle: _string(activity['title']) ?? 'Accès',
      relationship: _string(holder['relationship']) ?? '',
      singleUse: right['single_use'] == true,
      state: _string(right['state']),
      validFrom: _dateTime(right['valid_from']),
      validUntil: _dateTime(right['valid_until']),
      journeyId: _string(journey['id']),
      occurrenceStartsAt: _dateTime(timing['start_at']),
      occurrenceStartDate: _string(timing['start_date']),
      placeName: _string(place['name']) ?? _string(place['locality']),
      placeAddress: _string(place['address_line']),
      accessInstructions: _string(place['access_instructions']),
      dayOf: dayOf,
      capabilities: capabilities,
      freshness: base.freshness,
      sourceInvalidated: source.invalidated,
    );
  }

  static Map<String, dynamic> _map(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    return const {};
  }

  static List<String> _strings(Object? value) {
    if (value is! List) return const [];
    return value.map((item) => item.toString()).toList(growable: false);
  }

  static String? _string(Object? value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? null : text;
  }

  static DateTime? _dateTime(Object? value) {
    final text = _string(value);
    return text == null ? null : DateTime.tryParse(text);
  }
}
