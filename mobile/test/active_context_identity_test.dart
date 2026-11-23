import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/navigation/active_context_avatar.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/navigation/profile_avatar_image.dart';

import 'fakes.dart';

void main() {
  final personal = const PersonalActorContext();
  final spaceE = SpaceActorContext(
    space: SpaceActorIdentity(id: 'space-e', slug: 'artiste-e'),
  );
  final spaceR = SpaceActorContext(
    space: SpaceActorIdentity(id: 'space-r', slug: 'association-r'),
  );

  test('subscriptions and connections never inherit across contexts', () {
    expect(connectionsRouteForActor(personal), '/connections');
    expect(subscriptionRouteForActor(personal), '/billing');
    expect(connectionsRouteForActor(spaceE), '/space/artiste-e/connections');
    expect(subscriptionRouteForActor(spaceE), '/space/artiste-e/subscription');
    expect(
      subscriptionRouteForActor(spaceR),
      '/space/association-r/subscription',
    );
    expect(
      subscriptionRouteForActor(spaceR),
      isNot(subscriptionRouteForActor(spaceE)),
    );
  });

  test('cold start stays in the same context and semantic door', () {
    expect(restoredShellPath(personal, '/me'), '/me');
    expect(restoredShellPath(spaceE, '/space/us'), '/space/us');
    expect(restoredShellPath(spaceR, '/space/work'), '/space/work');
    expect(restoredShellPath(spaceR, '/ongoing'), '/space/work');
    expect(restoredShellPath(personal, '/space/us'), '/me');
    expect(restoredShellPath(spaceE, null), '/space/now');
  });

  test('Space monograms are presentation, not duplicated Profile data', () {
    expect(spaceMonogram('Kivu Digital Lab'), 'KD');
    expect(spaceMonogram('Artiste'), 'A');
    expect(
      activeSpaceName(spaceE.space, [
        SpaceSummary(
          identity: SpaceActorIdentity(id: 'space-e', slug: 'artiste-e'),
          name: 'Univers Artistique',
          archetype: 'generic',
          lifecycle: 'active',
          limitedToActivities: false,
        ),
      ]),
      'Univers Artistique',
    );
    expect(activeSpaceName(spaceR.space, null), 'association-r');
  });

  testWidgets('Space avatar never renders the personal portrait', (
    tester,
  ) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ActiveContextAvatar(
            runtime: runtime,
            actor: spaceE,
            size: 48,
            personalLetter: 'G',
            personalUrl: 'https://example.invalid/personal.jpg',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('A'), findsOneWidget);
    expect(find.text('G'), findsNothing);
    expect(find.byType(ProfileAvatarImage), findsNothing);
  });
}
