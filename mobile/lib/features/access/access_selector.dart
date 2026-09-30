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

  bool get isBeneficiary => relationship == 'beneficiary';

  bool get canOpenDayOf =>
      isBeneficiary && capabilities.contains('open_day_of') && dayOf != null;
}

class AccessDetailSelector {
  const AccessDetailSelector();

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
