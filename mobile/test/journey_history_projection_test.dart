import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/journey/journey_selector.dart';

void main() {
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
