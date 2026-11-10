import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/features/day_of/day_of_screen.dart';
import 'package:makolo_mobile/features/now/now_action_controller.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets('Day J only opens Live with an actual allowed handoff', (
    tester,
  ) async {
    var calls = 0;
    Future<void> render(bool enabled) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DayOfLiveAction(
              livePath: '/live/occurrence',
              remoteActionsAvailable: enabled,
              onOpenLive: (_) => calls++,
            ),
          ),
        ),
      );
    }

    await render(false);
    final disabled = tester.widget<MakoloActionButton>(
      find.byType(MakoloActionButton),
    );
    expect(disabled.phase, MakoloActionPhase.unavailable);
    await tester.tap(find.text('Voir la situation en direct'), warnIfMissed: false);
    expect(calls, 0);

    await render(true);
    expect(
      tester.widget<MakoloActionButton>(find.byType(MakoloActionButton)).phase,
      MakoloActionPhase.available,
    );
    await tester.tap(find.text('Voir la situation en direct'));
    expect(calls, 1);
  });

  testWidgets('Now uncertain decision cannot be posted twice before reread', (
    tester,
  ) async {
    const ownerId = '11111111-1111-4111-8111-111111111111';
    var attempted = 0;
    var refreshed = 0;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://example.test/'),
      tokenStore: MemoryTokenStore(
        session: const AuthSession(
          profileId: 'viewer',
          accessToken: 'test-access',
          refreshToken: 'test-refresh',
        ),
      ),
      dio: MockClient((request) async {
        if (request.url.path.endsWith('/accept/')) {
          attempted++;
          return const MockResponse('{"code":"server_error"}', 500);
        }
        return const MockResponse('{}', 404);
      }).dio,
    );
    addTearDown(api.close);

    const situation = NowSituationPresentation(
      identity: 'now:decision',
      reference: StructuredDestination(kind: 'now', id: ownerId),
      ownerDestination: StructuredDestination(
        kind: 'recognition_redemption',
        id: ownerId,
      ),
      humanContext: 'Demande',
      meaning: 'Une décision attend votre intervention.',
      emphasis: NowPresentationEmphasis.primary,
      businessActions: [
        NowBusinessActionPresentation(
          capability: 'accept',
          label: 'Accepter',
          href: '/api/v1/recognition/redemptions/$ownerId/accept/',
          confirmationRequired: true,
          interactionDepth: NowInteractionDepth.directNow,
        ),
      ],
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: NowActionRefreshScope(
            onRefresh: () async { refreshed++; },
            child: NowActionGroup(situation: situation, api: api),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Accepter'));
    await tester.pumpAndSettle();
    expect(attempted, 0);
    await tester.tap(find.text('Confirmer'));
    await tester.pump();
    await tester.runAsync(
      () async => Future<void>.delayed(const Duration(milliseconds: 30)),
    );
    await tester.pump();
    expect(attempted, 1);
    expect(find.text('Vérifier la situation'), findsOneWidget);

    // Even a second app tap cannot replay an uncertain owner mutation.
    await tester.tap(find.text('Accepter'), warnIfMissed: false);
    await tester.pump();
    expect(attempted, 1);

    // Rereading the owner-backed situation is an explicit, separate action.
    await tester.tap(find.text('Vérifier la situation'));
    await tester.pump();
    expect(refreshed, 1);
    expect(attempted, 1);
  });

  testWidgets('processing, failed and unavailable controls remain distinct', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              MakoloActionButton(
                label: 'Envoi en cours',
                icon: Icons.send_rounded,
                phase: MakoloActionPhase.processing,
                onPressed: () => calls++,
              ),
              MakoloActionButton(
                label: 'Revérifier',
                icon: Icons.refresh_rounded,
                phase: MakoloActionPhase.failed,
                onPressed: () => calls++,
              ),
              MakoloActionButton(
                label: 'Non disponible',
                phase: MakoloActionPhase.unavailable,
                onPressed: () => calls++,
              ),
            ],
          ),
        ),
      ),
    );
    await tester.tap(find.text('Envoi en cours'), warnIfMissed: false);
    await tester.tap(find.text('Non disponible'), warnIfMissed: false);
    expect(calls, 0);
    await tester.tap(find.text('Revérifier'));
    expect(calls, 1);
  });
}
