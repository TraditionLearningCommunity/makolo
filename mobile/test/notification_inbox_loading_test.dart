import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/notifications/notification_repository.dart';
import 'package:makolo_mobile/notifications/notification_screens.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';
import 'support/presentation_harness.dart';

void main() {
  testWidgets('no cache and API failure never leave a permanent spinner', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final store = ProfileStore(database, 'profile-a');
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'token',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      ),
      dio: MockClient(
        (_) async => MockResponse('{"detail":"Temporary outage"}', 500),
      ).dio,
    );
    final sync = SyncEngine(
      api: api,
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    final repository = NotificationRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await PresentationHarness.pump(
      tester,
      child: NotificationInboxScreen(
        repository: repository,
        onOpenDestination: (_) async {},
      ),
    );
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 150));
    });
    await tester.pump();
    await tester.pump();
    expect(find.byType(MakoloLoadingState), findsNothing);
    expect(find.byType(MakoloErrorState), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    api.close();
    await database.close();
  });
}
