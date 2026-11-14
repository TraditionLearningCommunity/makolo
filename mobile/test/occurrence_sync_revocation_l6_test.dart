import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/day_of/day_of_repository.dart';
import 'package:makolo_mobile/features/live/live_repository.dart';
import 'package:makolo_mobile/features/space/space_occurrence_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  Future<void> seed(ProfileStore store, String key) async {
    for (final kind in [
      DayOfRepository.projectionKind,
      LiveRepository.projectionKind,
    ]) {
      await store.putProjection(
        kind: kind,
        resourceKey: key,
        schemaVersion: 1,
        payload: {
          'identity': {'id': 'occ-a'},
          'private': 'last known',
        },
      );
    }
  }

  MakoloApiClient client(MockClient mock) => MakoloApiClient(
    baseUri: Uri.parse('https://makolo.invalid/'),
    tokenStore: MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    ),
    dio: mock.dio,
  );

  test('L6: denied Jour J purges sibling Live for same Profile only', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    await seed(store, 'occ-a');
    await seed(store, 'other-space|occ-a');
    final api = client(
      MockClient(
        (_) async => MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied'},
          }),
          403,
        ),
      ),
    );
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      database: db,
      store: store,
      profileId: 'profile-a',
    );
    final day = DayOfRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
    await expectLater(
      sync.pullSource(day.sourceFor('occ-a')),
      throwsA(isA<Exception>()),
    );
    expect(
      await store.readProjection(
        DayOfRepository.projectionKind,
        resourceKey: 'occ-a',
      ),
      isNull,
    );
    expect(
      await store.readProjection(
        LiveRepository.projectionKind,
        resourceKey: 'occ-a',
      ),
      isNull,
    );
    expect(
      await store.readProjection(
        LiveRepository.projectionKind,
        resourceKey: 'other-space|occ-a',
      ),
      isNotNull,
    );
  });

  test('L6: Live disabled does not withdraw still-authorized Jour J', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    await seed(store, 'occ-a');
    final api = client(
      MockClient(
        (_) async => MockResponse(
          jsonEncode({
            'error': {'code': 'not_found'},
          }),
          404,
        ),
      ),
    );
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      database: db,
      store: store,
      profileId: 'profile-a',
    );
    final live = LiveRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
    await expectLater(
      sync.pullSource(live.sourceFor('occ-a')),
      throwsA(isA<Exception>()),
    );
    expect(
      await store.readProjection(
        LiveRepository.projectionKind,
        resourceKey: 'occ-a',
      ),
      isNull,
    );
    expect(
      await store.readProjection(
        DayOfRepository.projectionKind,
        resourceKey: 'occ-a',
      ),
      isNotNull,
    );
  });

  test('L6: a transport failure retains last known, not authority', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    await seed(store, 'occ-a');
    final api = client(
      MockClient(
        (_) async =>
            const MockResponse('{"error":{"code":"server_unavailable"}}', 503),
      ),
    );
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      database: db,
      store: store,
      profileId: 'profile-a',
    );
    final day = DayOfRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
    await expectLater(
      sync.pullSource(day.sourceFor('occ-a')),
      throwsA(isA<Exception>()),
    );
    expect(
      await store.readProjection(
        DayOfRepository.projectionKind,
        resourceKey: 'occ-a',
      ),
      isNotNull,
    );
    expect(
      await store.readProjection(
        LiveRepository.projectionKind,
        resourceKey: 'occ-a',
      ),
      isNotNull,
    );
  });

  test('L6: denied Space A cannot purge personal or Space B facts', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    await seed(store, 'occ-a');
    await seed(store, 'space-a|occ-a');
    await seed(store, 'space-b|occ-a');
    final api = client(
      MockClient(
        (_) async => MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied'},
          }),
          403,
        ),
      ),
    );
    addTearDown(api.close);
    final sync = SyncEngine(
      api: api,
      database: db,
      store: store,
      profileId: 'profile-a',
    );
    final space = SpaceOccurrenceRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );
    final actor = SpaceActorIdentity(id: 'space-a', slug: 'a');
    await expectLater(
      sync.pullSource(space.dayOfSource(actor, 'occ-a')),
      throwsA(isA<Exception>()),
    );
    expect(
      await store.readProjection(
        LiveRepository.projectionKind,
        resourceKey: 'space-a|occ-a',
      ),
      isNull,
    );
    for (final key in ['occ-a', 'space-b|occ-a']) {
      expect(
        await store.readProjection(
          DayOfRepository.projectionKind,
          resourceKey: key,
        ),
        isNotNull,
      );
      expect(
        await store.readProjection(
          LiveRepository.projectionKind,
          resourceKey: key,
        ),
        isNotNull,
      );
    }
  });

  test(
    'L6: an in-flight Live response cannot rehydrate denied Jour J',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      await seed(store, 'occ-a');
      final liveStarted = Completer<void>();
      final releaseLive = Completer<void>();
      final api = client(
        MockClient((request) async {
          if (request.url.path.endsWith('/live/')) {
            liveStarted.complete();
            await releaseLive.future;
            return MockResponse(
              jsonEncode({
                'meta': {
                  'projection': 'occurrence.experience.live',
                  'schema_version': 1,
                  'scope': 'occurrence',
                  'generated_at': '2026-11-09T11:00:00Z',
                },
                'data': {
                  'identity': {'kind': 'occurrence', 'id': 'occ-a'},
                  'context': {
                    'viewer_profile_id': 'profile-a',
                    'actor_space_id': null,
                    'occurrence': {'id': 'occ-a'},
                  },
                  'surface': 'live',
                },
              }),
              200,
            );
          }
          return MockResponse(
            jsonEncode({
              'error': {'code': 'permission_denied'},
            }),
            403,
          );
        }),
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        database: db,
        store: store,
        profileId: 'profile-a',
      );
      final day = DayOfRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: sync,
      );
      final live = LiveRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
        sync: sync,
      );
      final pendingLive = sync.pullSource(live.sourceFor('occ-a'));
      await liveStarted.future;
      await expectLater(
        sync.pullSource(day.sourceFor('occ-a')),
        throwsA(isA<Exception>()),
      );
      releaseLive.complete();
      await pendingLive;
      expect(
        await store.readProjection(
          LiveRepository.projectionKind,
          resourceKey: 'occ-a',
        ),
        isNull,
      );
    },
  );
}
