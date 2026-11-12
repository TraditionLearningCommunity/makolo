import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/journey/journey_selector.dart';

void main() {
  test('Service result is distinct from the Journey lifecycle', () {
    final projection = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'service-under-review',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 12),
      payload: const {
        'representation': {'title': 'Ma demande de bourse'},
        'state': {'code': 'draft', 'label': 'En préparation'},
        'readiness': {
          'state': 'waiting',
          'ready': [],
          'actor_interventions': [],
          'waiting': [],
          'blockers': [],
        },
        'service_result': {'code': 'under_review', 'label': 'En revue'},
      },
    );
    final view = const JourneyDetailSelector().select(
      projection: projection,
      source: JourneySourceState.unknown,
      now: DateTime.utc(2026, 11, 12),
    );
    expect(view.serviceResult?.code, 'under_review');
    expect(view.serviceResult?.label, 'En revue');
    expect(view.journeyState, 'En préparation');
    expect(view.isTerminal, isFalse);
  });

  test('Journey N3 uses only owner history labels and dates', () {
    final projection = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-terminal',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 11),
      payload: const {
        'representation': {'title': 'Recevoir mon badge'},
        'state': {'code': 'fulfilled', 'label': 'Réalisée'},
        'readiness': {
          'state': 'ready',
          'ready': [],
          'actor_interventions': [],
          'waiting': [],
          'blockers': [],
        },
        'forms': [],
        'requirements': [],
        'capabilities': [],
        'history': [
          {
            'id': 'transition-1',
            'label': 'Réalisée',
            'state': 'fulfilled',
            'at': '2026-11-10T13:45:00+00:00',
          },
          {'id': 'invalid', 'reason': 'Never present private audit text'},
        ],
      },
    );
    final view = const JourneyDetailSelector().select(
      projection: projection,
      source: JourneySourceState.unknown,
      now: DateTime.utc(2026, 11, 11),
    );
    expect(view.isTerminal, isTrue);
    expect(view.history, hasLength(1));
    expect(view.history.first.label, 'Réalisée');
    expect(view.history.first.state, 'fulfilled');
    expect(view.history.first.at, DateTime.utc(2026, 11, 10, 13, 45));
  });
}
