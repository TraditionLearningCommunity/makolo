import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';

StoredProjection projection({
  Object? items = const [
    {
      'key': 'visa',
      'kind': 'journey.action',
      'dimension': 'action',
      'source': {'kind': 'journey', 'id': 'journey-1'},
      'state': 'action_required',
      'title': 'Visa Canada',
      'summary': 'Votre certificat doit être transmis aujourd’hui.',
      'timing': {'label': 'La fenêtre est ouverte aujourd’hui.'},
      'capabilities': ['open_detail'],
      'links': {'detail': '/api/v1/journeys/journey-1/'},
    },
  ],
  DateTime? freshUntil,
}) {
  return StoredProjection(
    kind: 'personal.now',
    schemaVersion: 1,
    payload: {'items': items},
    receivedAt: DateTime.utc(2026, 10, 3, 12),
    freshUntil: freshUntil,
  );
}

void main() {
  const selector = NowSelector();
  final now = DateTime.utc(2026, 10, 3, 14);

  test('adapts real personal.now shape without re-ranking', () {
    final result = selector.select(
      projection: projection(
        items: const [
          {
            'source': {'kind': 'journey', 'id': 'first'},
            'title': 'Premier',
            'summary': 'Conséquence première',
            'capabilities': [],
            'links': {},
          },
          {
            'source': {'kind': 'journey', 'id': 'second'},
            'title': 'Second',
            'summary': 'Conséquence seconde',
            'capabilities': [],
            'links': {},
          },
        ],
      ),
      now: now,
    );

    expect(result.state.availability, MakoloAvailabilityCue.content);
    expect(result.situations.map((item) => item.reference.id), [
      'first',
      'second',
    ]);
    expect(result.situations.first.emphasis.name, 'primary');
    expect(result.situations.last.emphasis.name, 'secondary');
  });

  test('server human context wins over the action title', () {
    final result = selector.select(
      projection: projection(
        items: const [
          {
            'source': {'kind': 'journey', 'id': 'journey-1'},
            'human_context': 'Visa Canada',
            'title': 'Transmettre le certificat',
            'summary': 'Votre certificat doit être transmis aujourd’hui.',
            'capabilities': [],
            'links': {},
          },
        ],
      ),
      now: now,
    );

    expect(result.situations.single.humanContext, 'Visa Canada');
    expect(
      result.situations.single.meaning,
      'Votre certificat doit être transmis aujourd’hui.',
    );
  });

  test('known empty projection is calm', () {
    final result = selector.select(
      projection: projection(items: const []),
      now: now,
    );

    expect(result.isCalm, isTrue);
    expect(result.state.availability, MakoloAvailabilityCue.empty);
  });

  test('missing projection is not calm', () {
    final result = selector.select(projection: null, now: now);

    expect(result.isCalm, isFalse);
    expect(result.state.availability, MakoloAvailabilityCue.initial);
  });

  test('malformed payload is a blocking failure, not all clear', () {
    final result = selector.select(
      projection: projection(items: const {'bad': 'shape'}),
      now: now,
    );

    expect(result.isCalm, isFalse);
    expect(result.state.failure, MakoloFailureCue.blocking);
  });

  test('non-empty malformed rows cannot become calm', () {
    final result = selector.select(
      projection: projection(
        items: const [
          {'title': 'Sans source'},
        ],
      ),
      now: now,
    );

    expect(result.isCalm, isFalse);
    expect(result.state.failure, MakoloFailureCue.blocking);
  });

  test('unknown capability never creates a CTA', () {
    final result = selector.select(
      projection: projection(
        items: const [
          {
            'source': {'kind': 'journey', 'id': 'journey-1'},
            'title': 'Visa Canada',
            'summary': 'Une action compte maintenant.',
            'capabilities': ['submit_required_document'],
            'links': {},
          },
        ],
      ),
      now: now,
    );

    expect(result.situations.single.responseCapability, isNull);
    expect(result.situations.single.responseLabel, isNull);
  });

  test('surface axes preserve offline, pending and stale independently', () {
    final result = selector.select(
      projection: projection(freshUntil: DateTime.utc(2026, 10, 3, 13)),
      now: now,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
      commit: MakoloCommitCue.pending,
      failure: MakoloFailureCue.recoverable,
    );

    expect(result.state.availability, MakoloAvailabilityCue.content);
    expect(
      result.state.reachability,
      MakoloReachabilityCue.temporarilyUnavailable,
    );
    expect(result.state.commit, MakoloCommitCue.pending);
    expect(result.state.failure, MakoloFailureCue.recoverable);
    expect(result.state.freshness, MakoloFreshnessCue.revalidationRequired);
  });
}
