import '../../data/local/profile_store.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import 'journey_repository.dart';

class JourneyReadinessItem {
  const JourneyReadinessItem({
    required this.key,
    required this.summary,
    this.reason,
    this.nextLabel,
    this.nextLink,
  });

  final String key;
  final String summary;
  final String? reason;
  final String? nextLabel;
  final String? nextLink;
}

class JourneyFormSummary {
  const JourneyFormSummary({
    required this.id,
    required this.required,
    required this.state,
    required this.canComplete,
    required this.detailLink,
    this.dueAt,
    this.saveLink,
    this.submitLink,
  });

  final String id;
  final bool required;
  final String state;
  final DateTime? dueAt;
  final bool canComplete;
  final String detailLink;
  final String? saveLink;
  final String? submitLink;
}

class JourneyReference {
  const JourneyReference({
    required this.id,
    required this.label,
    this.state,
    this.link,
  });

  final String id;
  final String label;
  final String? state;
  final String? link;
}

class JourneyDetailPresentation {
  const JourneyDetailPresentation({
    required this.available,
    required this.title,
    required this.kindLabel,
    required this.journeyState,
    required this.readinessState,
    required this.ready,
    required this.actorInterventions,
    required this.waiting,
    required this.blockers,
    required this.forms,
    required this.requirements,
    required this.capabilities,
    required this.freshness,
    required this.sourceInvalidated,
    this.summary,
    this.nextActionLabel,
    this.nextActionLink,
    this.resourcesLink,
    this.activity,
    this.occurrence,
    this.access,
    this.dayOfLink,
    this.liveLink,
  });

  final bool available;
  final String title;
  final String kindLabel;
  final String? summary;
  final String journeyState;
  final String readinessState;
  final List<JourneyReadinessItem> ready;
  final List<JourneyReadinessItem> actorInterventions;
  final List<JourneyReadinessItem> waiting;
  final List<JourneyReadinessItem> blockers;
  final String? nextActionLabel;
  final String? nextActionLink;
  final String? resourcesLink;
  final List<JourneyFormSummary> forms;
  final List<JourneyReference> requirements;
  final JourneyReference? activity;
  final JourneyReference? occurrence;
  final JourneyReference? access;
  final String? dayOfLink;
  final String? liveLink;
  final Set<String> capabilities;
  final FreshnessState? freshness;
  final bool sourceInvalidated;

  bool get canCompleteAnyForm => forms.any((form) => form.canComplete);
}

class JourneyDetailSelector {
  const JourneyDetailSelector();

  JourneyDetailPresentation select({
    required StoredProjection? projection,
    required JourneySourceState source,
    required DateTime now,
  }) {
    if (projection == null) {
      return JourneyDetailPresentation(
        available: false,
        title: '',
        kindLabel: 'Démarche',
        journeyState: '',
        readinessState: '',
        ready: const [],
        actorInterventions: const [],
        waiting: const [],
        blockers: const [],
        forms: const [],
        requirements: const [],
        capabilities: const {},
        freshness: null,
        sourceInvalidated: source.invalidated,
      );
    }

    final base = const ProjectionSelector().select(
      projection: projection,
      freshnessPolicy: JourneyRepository.freshnessPolicy,
      now: now,
      sourceInvalidated: source.invalidated,
    );
    final payload = base.payload ?? const <String, dynamic>{};
    final representation = _map(payload['representation']);
    final state = _map(payload['state']);
    final readiness = _map(payload['readiness']);
    final activity = _map(payload['activity']);
    final occurrence = _map(payload['occurrence']);
    final access = _map(payload['access']);
    final resources = _map(payload['resources']);
    final links = _map(payload['links']);
    final capabilities = _strings(payload['capabilities']).toSet();

    return JourneyDetailPresentation(
      available: true,
      title: _string(representation['title']) ?? 'Démarche',
      kindLabel: _string(representation['kind_label']) ?? 'Démarche',
      summary: _string(representation['summary']),
      journeyState: _string(state['label']) ?? _string(state['code']) ?? '',
      readinessState: _string(readiness['state']) ?? '',
      ready: _readinessItems(readiness['ready']),
      actorInterventions: _readinessItems(readiness['actor_interventions']),
      waiting: _readinessItems(readiness['waiting']),
      blockers: _readinessItems(readiness['blockers']),
      nextActionLabel: _string(_map(readiness['next'])['label']),
      nextActionLink: _string(_map(readiness['next'])['link']),
      resourcesLink: _string(resources['link']) ?? _string(links['resources']),
      forms: _forms(payload['forms']),
      requirements: _requirements(payload['requirements']),
      activity: activity.isEmpty
          ? null
          : JourneyReference(
              id: _string(activity['id']) ?? '',
              label: _string(activity['title']) ?? 'Activité',
              link: _string(links['activity']),
            ),
      occurrence: occurrence.isEmpty
          ? null
          : JourneyReference(
              id: _string(occurrence['id']) ?? '',
              label: _string(occurrence['label']) ?? 'Occurrence',
              state: _string(occurrence['state']),
              link: _string(links['occurrence']),
            ),
      access: access.isEmpty
          ? null
          : JourneyReference(
              id: _string(access['id']) ?? '',
              label: 'Accès',
              state: _string(access['state']),
              link: _string(access['link']),
            ),
      dayOfLink: capabilities.contains('open_day_of') && occurrence.isNotEmpty
          ? _string(links['day_of'])
          : null,
      liveLink: capabilities.contains('open_live') && occurrence.isNotEmpty
          ? _string(links['live'])
          : null,
      capabilities: capabilities,
      freshness: base.freshness,
      sourceInvalidated: source.invalidated,
    );
  }

  static List<JourneyReadinessItem> _readinessItems(Object? value) {
    return _maps(value)
        .map((row) {
          final next = _map(row['next']);
          return JourneyReadinessItem(
            key: _string(row['key']) ?? '',
            summary: _string(row['summary']) ?? _string(row['reason']) ?? '',
            reason: _string(row['reason']),
            nextLabel: _string(next['label']),
            nextLink: _string(next['link']),
          );
        })
        .toList(growable: false);
  }

  static List<JourneyFormSummary> _forms(Object? value) {
    return _maps(value)
        .map((row) {
          final links = _map(row['links']);
          final capabilities = _strings(row['capabilities']);
          return JourneyFormSummary(
            id: _string(row['id']) ?? '',
            required: row['required'] == true,
            state: _string(row['state']) ?? '',
            dueAt: _dateTime(row['due_at']),
            canComplete: capabilities.contains('complete_form'),
            detailLink: _string(links['detail']) ?? '',
            saveLink: _string(links['save']),
            submitLink: _string(links['submit']),
          );
        })
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }

  static List<JourneyReference> _requirements(Object? value) {
    return _maps(value)
        .map((row) {
          return JourneyReference(
            id: _string(row['id']) ?? '',
            label: _string(row['label']) ?? 'Requirement',
            state: _string(row['state']),
            link: _string(row['link']),
          );
        })
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }

  static Map<String, dynamic> _map(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    return const {};
  }

  static List<Map<String, dynamic>> _maps(Object? value) {
    if (value is! List) return const [];
    return value
        .map(_map)
        .where((row) => row.isNotEmpty)
        .toList(growable: false);
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
