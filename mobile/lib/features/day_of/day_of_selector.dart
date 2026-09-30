import '../../data/local/profile_store.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import 'day_of_repository.dart';

class DayOfDestination {
  const DayOfDestination({
    this.name,
    this.addressLine,
    this.locality,
    this.accessInstructions,
  });

  final String? name;
  final String? addressLine;
  final String? locality;
  final String? accessInstructions;
}

class DayOfAccessPresentation {
  const DayOfAccessPresentation({
    required this.id,
    required this.usable,
    required this.capabilities,
    this.state,
    this.credentialType,
    this.detailPath,
    this.credentialPath,
  });

  final String id;
  final String? state;
  final bool usable;
  final String? credentialType;
  final String? detailPath;
  final String? credentialPath;
  final Set<String> capabilities;

  bool get canOpenAccess =>
      capabilities.contains('open_access') && detailPath != null;

  bool get canPresentCredential =>
      capabilities.contains('present_credential') && credentialPath != null;
}

class DayOfQueuePresentation {
  const DayOfQueuePresentation({
    required this.id,
    this.label,
    this.state,
    this.position,
  });

  final String id;
  final String? label;
  final String? state;
  final int? position;
}

class DayOfPlacementPresentation {
  const DayOfPlacementPresentation({this.plan, this.unit, this.parentUnit});

  final String? plan;
  final String? unit;
  final String? parentUnit;
}

class DayOfCheckpointPresentation {
  const DayOfCheckpointPresentation({
    required this.id,
    this.label,
    this.state,
    this.blockedReason,
  });

  final String id;
  final String? label;
  final String? state;
  final String? blockedReason;
}

class DayOfPresentation {
  const DayOfPresentation({
    required this.available,
    required this.title,
    required this.capabilities,
    required this.accesses,
    required this.queue,
    required this.placements,
    required this.hazards,
    required this.actorInterventions,
    required this.blockers,
    required this.freshness,
    required this.sourceInvalidated,
    this.occurrenceLabel,
    this.occurrenceState,
    this.temporalRelation,
    this.nextLabel,
    this.destination,
    this.nextCheckpoint,
    this.livePath,
  });

  final bool available;
  final String title;
  final String? occurrenceLabel;
  final String? occurrenceState;
  final String? temporalRelation;
  final String? nextLabel;
  final DayOfDestination? destination;
  final DayOfCheckpointPresentation? nextCheckpoint;
  final String? livePath;
  final Set<String> capabilities;
  final List<DayOfAccessPresentation> accesses;
  final List<DayOfQueuePresentation> queue;
  final List<DayOfPlacementPresentation> placements;
  final List<String> hazards;
  final List<String> actorInterventions;
  final List<String> blockers;
  final FreshnessState? freshness;
  final bool sourceInvalidated;

  bool get canOpenLive =>
      capabilities.contains('open_live') && livePath != null;
}

class DayOfSelector {
  const DayOfSelector();

  DayOfPresentation select({
    required StoredProjection? projection,
    required DayOfSourceState source,
    required DateTime now,
  }) {
    if (projection == null) {
      return DayOfPresentation(
        available: false,
        title: '',
        capabilities: const {},
        accesses: const [],
        queue: const [],
        placements: const [],
        hazards: const [],
        actorInterventions: const [],
        blockers: const [],
        freshness: null,
        sourceInvalidated: source.invalidated,
      );
    }

    final base = const ProjectionSelector().select(
      projection: projection,
      freshnessPolicy: DayOfRepository.freshnessPolicy,
      now: now,
      sourceInvalidated: source.invalidated,
    );
    final payload = base.payload ?? const <String, dynamic>{};
    final activity = _map(payload['activity']);
    final occurrence = _map(payload['occurrence']);
    final situation = _map(payload['situation']);
    final spatial = _map(payload['spatial']);
    final destinationMap = _map(spatial['destination']);
    final readiness = _map(payload['readiness']);
    final checkpoints = _map(payload['checkpoints']);
    final nextCheckpointMap = _map(checkpoints['next']);
    final links = _map(payload['links']);

    return DayOfPresentation(
      available: true,
      title: _string(activity['title']) ?? 'Action en cours',
      occurrenceLabel: _string(occurrence['label']),
      occurrenceState: _string(occurrence['state']),
      temporalRelation: _string(situation['temporal_relation']),
      nextLabel: _string(_map(situation['next'])['label']),
      destination: destinationMap.isEmpty
          ? null
          : DayOfDestination(
              name: _string(destinationMap['name']),
              addressLine: _string(destinationMap['address_line']),
              locality: _string(destinationMap['locality']),
              accessInstructions: _string(
                destinationMap['access_instructions'],
              ),
            ),
      nextCheckpoint: nextCheckpointMap.isEmpty
          ? null
          : DayOfCheckpointPresentation(
              id: _string(nextCheckpointMap['id']) ?? '',
              label: _string(nextCheckpointMap['label']),
              state: _string(nextCheckpointMap['state']),
              blockedReason: _string(nextCheckpointMap['blocked_reason']),
            ),
      livePath: _string(links['live']),
      capabilities: _strings(payload['capabilities']).toSet(),
      accesses: _accesses(payload['access']),
      queue: _queue(payload['queue']),
      placements: _placements(payload['placement']),
      hazards: _maps(spatial['hazards'])
          .map((row) => _string(row['summary']))
          .whereType<String>()
          .toList(growable: false),
      actorInterventions: _readinessSummaries(readiness['actor_interventions']),
      blockers: _readinessSummaries(readiness['blockers']),
      freshness: base.freshness,
      sourceInvalidated: source.invalidated,
    );
  }

  static List<DayOfAccessPresentation> _accesses(Object? value) {
    return _maps(value)
        .map((row) {
          final credential = _map(row['credential']);
          final links = _map(row['links']);
          return DayOfAccessPresentation(
            id: _string(_map(row['identity'])['id']) ?? '',
            state: _string(row['state']),
            usable: row['usable'] == true,
            credentialType: _string(credential['type']),
            detailPath: _string(links['detail']),
            credentialPath: _string(links['credential']),
            capabilities: _strings(row['capabilities']).toSet(),
          );
        })
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }

  static List<DayOfQueuePresentation> _queue(Object? value) {
    return _maps(value)
        .map(
          (row) => DayOfQueuePresentation(
            id: _string(row['id']) ?? '',
            label: _string(row['label']),
            state: _string(row['state']),
            position: _integer(row['position']),
          ),
        )
        .where((row) => row.id.isNotEmpty)
        .toList(growable: false);
  }

  static List<DayOfPlacementPresentation> _placements(Object? value) {
    return _maps(value)
        .map(
          (row) => DayOfPlacementPresentation(
            plan: _string(row['plan']),
            unit: _string(row['unit']),
            parentUnit: _string(row['parent_unit']),
          ),
        )
        .toList(growable: false);
  }

  static List<String> _readinessSummaries(Object? value) {
    return _maps(value)
        .map((row) => _string(row['summary']))
        .whereType<String>()
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

  static int? _integer(Object? value) {
    if (value is int) return value;
    return int.tryParse(value?.toString() ?? '');
  }
}
