import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/now/now_action_controller.dart';
import 'package:makolo_mobile/features/now/now_proposal_decision.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

void main() {
  const id = '11111111-2222-4333-8444-555555555555';
  const owner = StructuredDestination(kind: 'recognition_redemption', id: id);
  const situation = NowSituationPresentation(
    identity: 'now:r',
    reference: owner,
    ownerDestination: owner,
    humanContext: 'Reconnaissance',
    meaning: 'Votre décision',
    emphasis: NowPresentationEmphasis.primary,
  );
  test('proposal focus does not infer authority from an arbitrary URL', () {
    const proposal = StructuredDestination(kind: 'action_proposal', id: id);
    const item = NowSituationPresentation(
      identity: 'now:proposal',
      reference: proposal,
      ownerDestination: proposal,
      humanContext: 'Proposition',
      meaning: 'Une réponse est demandée.',
      emphasis: NowPresentationEmphasis.primary,
    );
    const accepted = NowBusinessActionPresentation(
      capability: 'respond',
      label: 'Répondre',
      href: '/api/v1/social/action-proposals/$id/respond/',
      interactionDepth: NowInteractionDepth.focused,
    );
    const invalid = NowBusinessActionPresentation(
      capability: 'respond',
      label: 'Répondre',
      href: 'https://other.invalid/decision',
      interactionDepth: NowInteractionDepth.focused,
    );
    expect(
      NowProposalDecision.authorizedPath(item, accepted),
      'api/v1/social/action-proposals/$id/respond/',
    );
    expect(NowProposalDecision.authorizedPath(item, invalid), isNull);
  });

  test(
    'existing ticket owner APIs are callable only for the matching resource',
    () {
      for (final entry in [
        ('waitlist', 'accept', 'api/v1/tickets/waitlist/'),
        ('waitlist', 'leave', 'api/v1/tickets/waitlist/'),
        ('ticket_transfer', 'accept', 'api/v1/tickets/transfers/'),
        ('ticket_transfer', 'decline', 'api/v1/tickets/transfers/'),
      ]) {
        final scopedOwner = StructuredDestination(kind: entry.$1, id: id);
        final item = NowSituationPresentation(
          identity: 'now:${entry.$1}',
          reference: scopedOwner,
          ownerDestination: scopedOwner,
          humanContext: 'Décision',
          meaning: 'Une réponse est requise.',
          emphasis: NowPresentationEmphasis.primary,
        );
        final action = NowBusinessActionPresentation(
          capability: entry.$2,
          label: 'Confirmer',
          href: '/${entry.$3}$id/${entry.$2}/',
          interactionDepth: NowInteractionDepth.directNow,
          confirmationRequired: true,
        );
        expect(
          NowOwnerAction.authorizedPath(item, action),
          '${entry.$3}$id/${entry.$2}/',
        );
      }
    },
  );

  test('owner-issued direct decision is the only callable action', () {
    const allowed = NowBusinessActionPresentation(
      capability: 'accept',
      label: 'Accepter',
      href: '/api/v1/recognition/redemptions/$id/accept/',
      interactionDepth: NowInteractionDepth.directNow,
      confirmationRequired: true,
    );
    expect(
      NowOwnerAction.authorizedPath(situation, allowed),
      'api/v1/recognition/redemptions/$id/accept/',
    );
    const unconfirmed = NowBusinessActionPresentation(
      capability: 'accept',
      label: 'Accepter',
      href: '/api/v1/recognition/redemptions/$id/accept/',
      interactionDepth: NowInteractionDepth.directNow,
    );
    expect(NowOwnerAction.authorizedPath(situation, unconfirmed), isNull);
    const wrong = NowBusinessActionPresentation(
      capability: 'accept',
      label: 'Accepter',
      href: '/api/v1/recognition/redemptions/$id/decline/',
      interactionDepth: NowInteractionDepth.directNow,
      confirmationRequired: true,
    );
    expect(NowOwnerAction.authorizedPath(situation, wrong), isNull);
  });
}
