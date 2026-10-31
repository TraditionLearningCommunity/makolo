import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/now/now_action_controller.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

StoredProjection _spaceNowProjection(List<Object?> items) => StoredProjection(
  kind: 'space.now',
  schemaVersion: 1,
  payload: <String, dynamic>{
    'surface': 'now_space',
    'actor': {'type': 'space', 'id': 'space-a'},
    'viewer': {'type': 'profile', 'id': 'viewer-a'},
    'selection': {'state': 'partial', 'reason': 'owner_coverage_incomplete'},
    'actor_attention_state': items.isEmpty ? 'unknown' : 'active',
    'freshness': {'state': 'unknown'},
    'items': items,
  },
  receivedAt: DateTime.utc(2026, 10, 31, 12),
);

void main() {
  final observedAt = DateTime.utc(2026, 10, 31, 12, 5);
  const selector = NowSelector();

  test('empty Space Now with partial coverage never becomes calm', () {
    final result = selector.select(
      projection: _spaceNowProjection(const []),
      now: observedAt,
    );
    expect(result.isCalm, isFalse);
    expect(result.situations, isEmpty);
    expect(result.selectionState, 'partial');
    expect(result.state.failure, MakoloFailureCue.recoverable);
  });

  test('Space Journey depth only accepts a relative owner path', () {
    const authorized = StructuredDestination(
      kind: 'space_work_journey',
      id: 'journey-a',
      link: '/space/space-a/retrieval/journey/journey-a',
    );
    const foreignLink = StructuredDestination(
      kind: 'space_work_journey',
      id: 'journey-a',
      link: 'https://external.invalid/space/space-a/retrieval/journey/journey-a',
    );
    expect(
      NowScreen.ownerPathFor(authorized),
      '/space/space-a/retrieval/journey/journey-a',
    );
    expect(NowScreen.ownerPathFor(foreignLink), isNull);
  });

  test('Space owner situation uses common Now semantics without direct POST', () {
    final result = selector.select(
      projection: _spaceNowProjection([
        {
          'id': 'space-now:space-a:journey_request:req-a',
          'human_context': 'Inscription',
          'source': {'kind': 'journey_request', 'id': 'req-a'},
          'subject': {'label': 'Demande en attente'},
          'state_meaning': 'Demande reçue, en attente de décision',
          'why_now': {
            'reason': 'journey_request_pending',
            'meaning': 'Une demande attend une décision.',
          },
          'consequence': {'state': 'unknown', 'effect': null},
          'response': {'type': 'decide', 'label': 'Examiner la demande'},
          'handoffs': [
            {'type': 'owner', 'target': 'space_request', 'id': 'req-a'},
          ],
          'business_actions': [
            {
              'capability': 'open_owner',
              'label': 'Examiner la demande',
              'href': '/spaces/test/requests/',
              'interaction_depth': 'domain_depth',
              'confirmation_required': false,
            },
          ],
        },
      ]),
      now: observedAt,
    );
    expect(result.situations, hasLength(1));
    final situation = result.situations.single;
    expect(situation.whyNowReason, 'journey_request_pending');
    expect(situation.consequence, isNull);
    expect(situation.consequenceState, 'unknown');
    expect(situation.ownerDestination?.kind, 'space_request');
    expect(NowScreen.ownerPathFor(situation.ownerDestination!), '/space/requests/req-a');
    expect(situation.businessActions, hasLength(1));
    final action = situation.businessActions.single;
    expect(action.interactionDepth, NowInteractionDepth.domainDepth);
    expect(NowOwnerAction.authorizedPath(situation, action), isNull);
  });
}
