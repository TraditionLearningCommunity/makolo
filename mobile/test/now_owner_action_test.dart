import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/now/now_action_controller.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

void main() {
  const id = '11111111-2222-4333-8444-555555555555';
  const owner = StructuredDestination(kind: 'recognition_redemption', id: id);
  const situation = NowSituationPresentation(identity: 'now:r', reference: owner, ownerDestination: owner, humanContext: 'Reconnaissance', meaning: 'Votre décision', emphasis: NowPresentationEmphasis.primary);
  test('owner-issued direct decision is the only callable action', () {
    const allowed = NowBusinessActionPresentation(capability: 'accept', label: 'Accepter', href: '/api/v1/recognition/redemptions/$id/accept/', interactionDepth: NowInteractionDepth.directNow, confirmationRequired: true);
    expect(NowOwnerAction.authorizedPath(situation, allowed), 'api/v1/recognition/redemptions/$id/accept/');
    const unconfirmed = NowBusinessActionPresentation(capability: 'accept', label: 'Accepter', href: '/api/v1/recognition/redemptions/$id/accept/', interactionDepth: NowInteractionDepth.directNow);
    expect(NowOwnerAction.authorizedPath(situation, unconfirmed), isNull);
    const wrong = NowBusinessActionPresentation(capability: 'accept', label: 'Accepter', href: '/api/v1/recognition/redemptions/$id/decline/', interactionDepth: NowInteractionDepth.directNow, confirmationRequired: true);
    expect(NowOwnerAction.authorizedPath(situation, wrong), isNull);
  });
}
