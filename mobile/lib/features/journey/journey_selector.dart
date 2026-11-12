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

/// Non-actionable owner facts are not turned into client-side commands.
class JourneyPaymentSummary {
  const JourneyPaymentSummary({
    required this.amount,
    required this.currency,
    required this.state,
    this.reason,
    this.obligationId,
    this.orderId,
  });
  final String amount;
  final String currency;
  final String state;
  final String? reason;
  final String? obligationId;
  final String? orderId;
}

class JourneyHistoryEntry {
  const JourneyHistoryEntry({
    required this.id,
    required this.label,
    required this.state,
    required this.at,
  });

  final String id;
  final String label;
  final String state;
  final DateTime at;
}

class JourneyOrderSummary {
  const JourneyOrderSummary({
    required this.id,
    required this.state,
    this.total,
    this.currency,
  });

  final String id;
  final String state;
  final String? total;
  final String? currency;
}

class JourneyPracticalFacts {
  const JourneyPracticalFacts({
    this.startAt,
    this.startDate,
    this.startTime,
    this.endDate,
    this.endTime,
    this.timezone,
    this.placeName,
    this.placeAddress,
    this.placeLocality,
    this.accessInstructions,
  });
  final DateTime? startAt;
  final String? startDate;
  final String? startTime;
  final String? endDate;
  final String? endTime;
  final String? timezone;
  final String? placeName;
  final String? placeAddress;
  final String? placeLocality;
  final String? accessInstructions;

  bool get hasContent =>
      startAt != null ||
      startDate != null ||
      placeName != null ||
      placeAddress != null ||
      accessInstructions != null;
}

class JourneyResourcePreview {
  const JourneyResourcePreview({
    required this.id,
    required this.title,
    required this.kind,
    this.description,
    this.mimeType,
  });
  final String id;
  final String title;
  final String kind;
  final String? description;
  final String? mimeType;

  static List<JourneyResourcePreview> fromProjection(
    StoredProjection? projection,
  ) {
    final raw = projection?.payload['items'];
    if (raw is! List) return const [];
    final rows = <JourneyResourcePreview>[];
    for (final item in raw) {
      if (item is! Map) continue;
      final id = item['id']?.toString().trim() ?? '';
      final title = item['title']?.toString().trim() ?? '';
      if (id.isEmpty || title.isEmpty) continue;
      final kind = item['kind']?.toString() ?? '';
      final description = item['description']?.toString().trim();
      rows.add(
        JourneyResourcePreview(
          id: id,
          title: title,
          kind: kind,
          description: description?.isNotEmpty == true ? description : null,
          mimeType: item['mime_type']?.toString(),
        ),
      );
    }
    return List.unmodifiable(rows);
  }
}

/// A JourneyStep is an owner fact, never a locally invented task or percentage.
class JourneyStepSummary {
  const JourneyStepSummary({
    required this.id,
    required this.title,
    required this.status,
    required this.kind,
    required this.dependsOn,
  });

  final String id;
  final String title;
  final String status;
  final String kind;
  final List<String> dependsOn;

  bool get isCompleted => status == 'completed';
  bool get isTerminal =>
      status == 'completed' || status == 'skipped' || status == 'cancelled';
}

class JourneyFormSummary {
  const JourneyFormSummary({
    required this.id,
    required this.required,
    required this.state,
    required this.canComplete,
    required this.detailLink,
    this.title = 'Formulaire',
    this.dueAt,
    this.saveLink,
    this.submitLink,
  });

  final String id;
  final String title;
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
    this.isRequired = false,
    this.consequence,
  });

  final String id;
  final String label;
  final String? state;
  final String? link;
  final bool isRequired;
  final String? consequence;
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
    this.canRespondInvitation = false,
    this.pendingRequests = 0,
    this.rejectedRequests = 0,
    this.payment,
    this.order,
    this.history = const [],
    this.payments = const [],
    this.practical,
    this.workflowKind = '',
    this.stateCode = '',
    this.steps = const [],
    this.summary,
    this.nextActionLabel,
    this.nextActionKey,
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
  final String workflowKind;
  final String stateCode;
  final List<JourneyStepSummary> steps;
  final String? summary;
  final String journeyState;
  final String readinessState;
  final List<JourneyReadinessItem> ready;
  final List<JourneyReadinessItem> actorInterventions;
  final List<JourneyReadinessItem> waiting;
  final List<JourneyReadinessItem> blockers;
  final String? nextActionLabel;
  final String? nextActionKey;
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
  final bool canRespondInvitation;
  final int pendingRequests;
  final int rejectedRequests;
  final JourneyPaymentSummary? payment;
  final JourneyOrderSummary? order;
  final List<JourneyHistoryEntry> history;
  final List<JourneyPaymentSummary> payments;
  final JourneyPracticalFacts? practical;

  bool get canCompleteAnyForm => forms.any((form) => form.canComplete);
  bool get isTerminal => const {
    'fulfilled',
    'rejected',
    'cancelled',
    'expired',
  }.contains(stateCode);
}

class JourneyDetailSelector {
  const JourneyDetailSelector();

  JourneyDetailPresentation select({
    required StoredProjection? projection,
    required JourneySourceState source,
    required DateTime now,
  }) {
    // An explicit owner denial is authoritative even if a stale snapshot
    // is still in a stream during SQLite invalidation.
    final ownerDenied =
        source.invalidated &&
        const {'permission_denied', 'not_found'}.contains(source.lastErrorCode);
    if (projection == null || ownerDenied) {
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
    final identity = _map(payload['identity']);
    final representation = _map(payload['representation']);
    final state = _map(payload['state']);
    final readiness = _map(payload['readiness']);
    final activity = _map(payload['activity']);
    final occurrence = _map(payload['occurrence']);
    final access = _map(payload['access']);
    final resources = _map(payload['resources']);
    final links = _map(payload['links']);
    final requests = _map(payload['requests']);
    final capabilities = _strings(payload['capabilities']).toSet();

    final title = _string(representation['title']) ?? 'Démarche';
    final summary = _string(representation['summary']);
    return JourneyDetailPresentation(
      available: true,
      title: title,
      kindLabel: _string(representation['kind_label']) ?? 'Démarche',
      workflowKind: _string(identity['workflow']) ?? '',
      stateCode: _string(state['code']) ?? '',
      steps: _steps(payload['steps']),
      pendingRequests: _maps(requests['pending']).length,
      rejectedRequests: _maps(requests['rejected']).length,
      payment: _payment(payload['payment']),
      order: _order(payload['payment']),
      history: _history(payload['history']),
      payments: _payments(payload['payment']),
      practical: _practical(occurrence),
      summary: summary != null && summary.toLowerCase() != title.toLowerCase()
          ? summary
          : null,
      journeyState: _string(state['label']) ?? _string(state['code']) ?? '',
      readinessState: _string(readiness['state']) ?? '',
      ready: _readinessItems(readiness['ready']),
      actorInterventions: _readinessItems(readiness['actor_interventions']),
      waiting: _readinessItems(readiness['waiting']),
      blockers: _readinessItems(readiness['blockers']),
      nextActionLabel: _string(_map(readiness['next'])['label']),
      nextActionKey: _string(_map(readiness['next'])['key']),
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
      canRespondInvitation:
          capabilities.contains('accept_invitation') &&
          capabilities.contains('decline_invitation') &&
          _string(links['invitation']) != null,
      freshness: base.freshness,
      sourceInvalidated: source.invalidated,
    );
  }

  static List<JourneyHistoryEntry> _history(Object? value) {
    return _maps(value)
        .map((row) {
          final id = _string(row['id']);
          final label = _string(row['label']);
          final state = _string(row['state']);
          final at = _dateTime(row['at']);
          if (id == null || label == null || state == null || at == null) {
            return null;
          }
          return JourneyHistoryEntry(
            id: id,
            label: label,
            state: state,
            at: at,
          );
        })
        .whereType<JourneyHistoryEntry>()
        .toList(growable: false);
  }

  static JourneyOrderSummary? _order(Object? value) {
    final order = _map(_map(value)['order']);
    final id = _string(order['id']);
    final state = _string(order['state']);
    if (id == null || state == null) return null;
    return JourneyOrderSummary(
      id: id,
      state: state,
      total: _string(order['total']),
      currency: _string(order['currency']),
    );
  }

  static List<JourneyPaymentSummary> _payments(Object? value) {
    final payload = _map(value);
    if (payload.isEmpty) return const [];
    final obligations = _maps(payload['obligations']);
    if (obligations.isNotEmpty) {
      return List.unmodifiable([
        for (final row in obligations)
          if (_string(row['amount']) != null &&
              _string(row['currency']) != null &&
              _string(row['state']) != null)
            JourneyPaymentSummary(
              amount: _string(row['amount'])!,
              currency: _string(row['currency'])!,
              // The obligation owns its state. A payment attempt cannot
              // silently mark an unpaid obligation as settled.
              state: _string(row['state'])!,
              reason: _string(row['reason']),
              obligationId: _string(row['id']),
            ),
      ]);
    }
    final single = _payment(value);
    return single == null ? const [] : [single];
  }

  static JourneyPaymentSummary? _payment(Object? value) {
    final payment = _map(value);
    if (payment.isEmpty) return null;
    final order = _map(payment['order']);
    final latest = _map(payment['payment']);
    final obligations = _maps(payment['obligations']);
    final obligation = obligations.isEmpty
        ? const <String, dynamic>{}
        : obligations.first;
    final amount = _string(obligation['amount']) ?? _string(order['total']);
    final currency =
        _string(obligation['currency']) ?? _string(order['currency']);
    final state =
        _string(obligation['state']) ??
        _string(order['state']) ??
        _string(_map(obligation['payment'])['state']) ??
        _string(latest['state']);
    if (amount == null || currency == null || state == null) return null;
    return JourneyPaymentSummary(
      amount: amount,
      currency: currency,
      state: state,
      reason: _string(obligation['reason']),
      obligationId: _string(obligation['id']),
      orderId: _string(order['id']),
    );
  }

  static JourneyPracticalFacts? _practical(Map<String, dynamic> occurrence) {
    if (occurrence.isEmpty) return null;
    final timing = _map(occurrence['timing']);
    final place = _map(occurrence['place']);
    final result = JourneyPracticalFacts(
      startAt: _dateTime(timing['start_at']),
      startDate: _string(timing['start_date']),
      startTime: _string(timing['start_time']),
      endDate: _string(timing['end_date']),
      endTime: _string(timing['end_time']),
      timezone: _string(timing['timezone']),
      placeName: _string(place['name']),
      placeAddress: _string(place['address']),
      placeLocality: _string(place['locality']),
      accessInstructions: _string(place['instructions']),
    );
    return result.hasContent ? result : null;
  }

  static List<JourneyStepSummary> _steps(Object? value) {
    return _maps(value)
        .map((row) {
          return JourneyStepSummary(
            id: _string(row['id']) ?? '',
            title: _string(row['title']) ?? '',
            status: _string(row['status']) ?? '',
            kind: _string(row['kind']) ?? '',
            dependsOn: _strings(row['depends_on']),
          );
        })
        .where((step) => step.id.isNotEmpty && step.title.isNotEmpty)
        .toList(growable: false);
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
            title: _string(row['title']) ?? 'Formulaire',
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
            isRequired: row['required'] == true,
            consequence: _string(row['consequence']),
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
