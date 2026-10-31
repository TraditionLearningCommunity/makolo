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

  test('Space Activity and Commerce owner paths enforce scoped shape', () {
    const activity = StructuredDestination(
      kind: 'space_work_activity',
      id: 'activity-1',
      link: '/space/space-a/retrieval/activity/activity-1',
    );
    const order = StructuredDestination(
      kind: 'space_commerce_order',
      id: 'order-1',
      link: '/space/space-a/retrieval/commerce_order/order-1',
    );
    const changedKind = StructuredDestination(
      kind: 'space_commerce_order',
      id: 'order-1',
      link: '/space/space-a/retrieval/activity/order-1',
    );
    const absolute = StructuredDestination(
      kind: 'space_work_activity',
      id: 'activity-1',
      link: 'https://untrusted.example/space/space-a/retrieval/activity/activity-1',
    );
    const query = StructuredDestination(
      kind: 'space_work_activity',
      id: 'activity-1',
      link: '/space/space-a/retrieval/activity/activity-1?bypass=1',
    );
    expect(
      NowScreen.ownerPathFor(activity),
      '/space/space-a/retrieval/activity/activity-1',
    );
    expect(
      NowScreen.ownerPathFor(order),
      '/space/space-a/retrieval/commerce_order/order-1',
    );
    expect(NowScreen.ownerPathFor(changedKind), isNull);
    expect(NowScreen.ownerPathFor(absolute), isNull);
    expect(NowScreen.ownerPathFor(query), isNull);
  });

  test('Cross-domain Space signals stay owner-backed and do not claim calm', () {
    final result = selector.select(
      projection: _spaceNowProjection([
        {
          'id': 'space-now:space-a:payment:payment-1',
          'source': {'kind': 'payment', 'id': 'payment-1'},
          'human_context': 'Commande C-10',
          'state_meaning': 'Dernière tentative de paiement échouée',
          'why_now': {
            'reason': 'payment_failed_order_pending',
            'meaning': 'Le paiement a échoué alors que la commande attend.',
          },
          'consequence': {'state': 'unknown'},
          'response': {'type': 'monitor'},
          'handoffs': [
            {
              'type': 'owner',
              'target': 'space_commerce_order',
              'id': 'order-1',
              'link': '/space/space-a/retrieval/commerce_order/order-1',
            },
          ],
          'business_actions': [
            {
              'capability': 'open_owner',
              'label': 'Vérifier le paiement',
              'href': '/spaces/space-a/payments/',
              'interaction_depth': 'domain_depth',
              'confirmation_required': false,
            },
          ],
        },
      ]),
      now: observedAt,
    );
    expect(result.isCalm, isFalse);
    expect(result.situations, hasLength(1));
    final item = result.situations.single;
    expect(item.whyNowReason, 'payment_failed_order_pending');
    expect(item.consequenceState, 'unknown');
    expect(item.ownerDestination?.kind, 'space_commerce_order');
    expect(
      NowScreen.ownerPathFor(item.ownerDestination!),
      '/space/space-a/retrieval/commerce_order/order-1',
    );
    expect(item.businessActions.single.interactionDepth,
        NowInteractionDepth.domainDepth);
  });

  test('Space payer obligations use a strictly scoped native owner link', () {
    const owned = StructuredDestination(
      kind: 'space_payment_obligation',
      id: 'obligation-1',
      link: '/space/space-a/retrieval/payment_obligation/obligation-1',
    );
    const wrongOwner = StructuredDestination(
      kind: 'space_payment_obligation',
      id: 'obligation-1',
      link: '/space/space-a/retrieval/commerce_order/obligation-1',
    );
    const external = StructuredDestination(
      kind: 'space_payment_obligation',
      id: 'obligation-1',
      link: 'https://untrusted.example/space/space-a/retrieval/payment_obligation/obligation-1',
    );
    expect(
      NowScreen.ownerPathFor(owned),
      '/space/space-a/retrieval/payment_obligation/obligation-1',
    );
    expect(NowScreen.ownerPathFor(wrongOwner), isNull);
    expect(NowScreen.ownerPathFor(external), isNull);
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
