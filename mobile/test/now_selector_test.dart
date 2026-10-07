import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

StoredProjection projection({
  Object? items = const [
    {
      'id': 'now:visa:certificate',
      'human_context': 'Visa Canada',
      'state': 'journey.step.action_required',
      'state_meaning': 'Votre certificat doit être transmis aujourd’hui.',
      'why_now': {
        'reason': 'journey.step.action_required',
        'meaning': 'La fenêtre est ouverte aujourd’hui.',
        'basis': [],
      },
      'consequence': {
        'state': 'unknown',
        'effect': null,
        'target': {'kind': 'journey', 'id': 'journey:visa'},
      },
      'turn': {'type': 'profile'},
      'response': {'type': 'act', 'label': 'Vérifier et envoyer'},
      'handoffs': [
        {'type': 'owner', 'target': 'journey', 'id': 'journey:visa'},
      ],
    },
  ],
  DateTime? freshUntil,
}) {
  return StoredProjection(
    kind: 'personal.now',
    schemaVersion: 1,
    payload: {
      'freshness': {'state': 'fresh'},
      'selection': {
        'state': items is List && items.isEmpty ? 'empty' : 'ready',
      },
      'actor_attention_state': items is List && items.isEmpty
          ? 'calm'
          : 'active',
      'items': items,
      'continuation': null,
      'terminal': {'state': items is List && items.isEmpty ? 'empty' : 'ok'},
    },
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
            'id': 'now:first',
            'human_context': 'Premier',
            'state': 'Conséquence première',
          },
          {
            'id': 'now:second',
            'human_context': 'Second',
            'state': 'Conséquence seconde',
          },
        ],
      ),
      now: now,
    );

    expect(result.state.availability, MakoloAvailabilityCue.content);
    expect(result.situations.map((item) => item.identity), [
      'now:first',
      'now:second',
    ]);
    expect(result.situations.first.emphasis.name, 'primary');
    expect(result.situations.last.emphasis.name, 'secondary');
  });

  test('server human context wins over the action title', () {
    final result = selector.select(
      projection: projection(
        items: const [
          {
            'id': 'now:journey-1',
            'human_context': 'Visa Canada',
            'state': 'Votre certificat doit être transmis aujourd’hui.',
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
          {'state': 'Sans identité'},
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
            'id': 'now:journey-1',
            'human_context': 'Visa Canada',
            'state': 'Une action compte maintenant.',
            'capabilities': ['submit_required_document'],
          },
        ],
      ),
      now: now,
    );

    expect(result.situations.single.responseCapability, isNull);
    expect(result.situations.single.responseLabel, isNull);
  });

  test('consumes C0 semantics without rebuilding them', () {
    final result = selector.select(projection: projection(), now: now);
    final situation = result.situations.single;

    expect(situation.identity, 'now:visa:certificate');
    expect(situation.serverState, 'journey.step.action_required');
    expect(
      situation.meaning,
      'Votre certificat doit être transmis aujourd’hui.',
    );
    expect(situation.whyNow, 'La fenêtre est ouverte aujourd’hui.');
    expect(situation.whyNowReason, 'journey.step.action_required');
    expect(situation.consequence, isNull);
    expect(situation.consequenceState, 'unknown');
    expect(situation.turn, 'profile');
    expect(situation.responseType, 'act');
    expect(situation.responseLabel, 'Vérifier et envoyer');
    expect(situation.ownerDestination?.kind, 'journey');
    expect(situation.ownerDestination?.id, 'journey:visa');
    expect(result.serverFreshnessState, 'fresh');
    expect(result.actorAttentionState, 'active');
    expect(result.continuation.state, NowContinuationState.end);
  });

  test('empty items do not imply calm when server selection is not empty', () {
    final value = projection(items: const []);
    final result = selector.select(
      projection: StoredProjection(
        kind: value.kind,
        schemaVersion: value.schemaVersion,
        payload: {
          ...value.payload,
          'selection': {'state': 'partial'},
          'terminal': {'state': 'unavailable'},
        },
        receivedAt: value.receivedAt,
        freshUntil: value.freshUntil,
      ),
      now: now,
    );

    expect(result.isCalm, isFalse);
    expect(result.selectionState, 'partial');
    expect(result.state.failure, MakoloFailureCue.recoverable);
  });

  test('keeps an opaque continuation token without interpreting it', () {
    final value = projection();
    final result = selector.select(
      projection: StoredProjection(
        kind: value.kind,
        schemaVersion: value.schemaVersion,
        payload: {
          ...value.payload,
          'continuation': {'state': 'MORE', 'token': 'opaque:next'},
        },
        receivedAt: value.receivedAt,
        freshUntil: value.freshUntil,
      ),
      now: now,
    );

    expect(result.continuation.state, NowContinuationState.more);
    expect(result.continuation.token, 'opaque:next');
    expect(result.situations.single.identity, 'now:visa:certificate');
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
