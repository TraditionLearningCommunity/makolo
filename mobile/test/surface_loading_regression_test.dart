import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/sync_lifecycle.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_screens.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/ongoing/ongoing_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

import 'dio_testing.dart';
import 'fakes.dart';
import 'support/presentation_harness.dart';

void main() {
  for (final surface in ['now', 'ongoing', 'discovery']) {
    group(surface, () {
      late MakoloDatabase database;
      late ProfileStore store;
      late MakoloApiClient api;
      late SyncEngine sync;
      late PersonalRepository repository;
      late DiscoveryRepository discovery;
      setUp(() async {
        database = MakoloDatabase.memory();
        store = ProfileStore(database, 'profile-a');
        final tokens = MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'test',
            refreshToken: 'test',
            profileId: 'profile-a',
          ),
        );
        api = MakoloApiClient(
          baseUri: Uri.parse('https://example.test/'),
          tokenStore: tokens,
          dio: MockClient(
            (_) async => MockResponse('{"code":"server_error"}', 500),
          ).dio,
        );
        sync = SyncEngine(
          api: api,
          store: store,
          database: database,
          profileId: 'profile-a',
        );
        repository = PersonalRepository(store);
        discovery = DiscoveryRepository(
          database: database,
          store: store,
          profileId: 'profile-a',
          api: api,
          sync: sync,
        );
        try {
          if (surface == 'discovery') {
            await sync.pullSource(
              discovery.itemsSource(const DiscoveryQuery()),
            );
          } else {
            await sync.pull(SyncEngine.roots[surface == 'now' ? 0 : 1]);
          }
          fail('HTTP 500 must fail acquisition');
        } catch (error) {
          expect(error, isA<MakoloApiError>());
        }
      });
      tearDown(() async {
        api.close();
        await database.close();
      });
      testWidgets('API 500 without snapshot ends loading and offers recovery', (
        tester,
      ) async {
        var retries = 0;
        final Widget screen = switch (surface) {
          'now' => NowScreen(repository: repository, sync: sync),
          'ongoing' => OngoingScreen(repository: repository),
          _ => DiscoveryScreen(
            repository: discovery,
            onOpenActivity: (_) {},
            onOpenItem: (_, _) {},
          ),
        };
        await PresentationHarness.pump(
          tester,
          child: SyncRefreshScope(
            refresh: () async {
              retries++;
            },
            child: SyncStatusScope(
              status: const SyncStatus(state: SyncVisualState.synced),
              child: screen,
            ),
          ),
        );
        await tester.runAsync(() async {
          await Future<void>.delayed(const Duration(milliseconds: 100));
        });
        await tester.pump();
        await tester.pump();
        expect(find.byType(MakoloSkeleton), findsNothing);
        expect(find.byType(MakoloErrorState), findsOneWidget);
        expect(find.text('Réessayer'), findsOneWidget);
        // Without an offline snapshot, never claim any data was preserved.
        expect(find.textContaining('conservées'), findsNothing);
        if (surface != 'discovery') {
          await tester.tap(find.text('Réessayer'));
          expect(retries, 1);
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump(const Duration(milliseconds: 1));
        await tester.pump(const Duration(milliseconds: 1));
        await tester.runAsync(database.close);
      });
    });
  }
}
