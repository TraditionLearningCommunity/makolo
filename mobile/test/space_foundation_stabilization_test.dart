import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';

class _ActorStore implements ActorContextStore {
  final Map<String, ActorContext> values = <String, ActorContext>{};

  @override
  Future<ActorContext> readActorContext(String profileId) async =>
      values[profileId] ?? const PersonalActorContext();

  @override
  Future<void> writeActorContext(String profileId, ActorContext context) async {
    values[profileId] = context;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    values.remove(profileId);
  }
}

class _Harness {
  _Harness({
    required this.database,
    required this.store,
    required this.actorContext,
    required this.repository,
  });

  final MakoloDatabase database;
  final ProfileStore store;
  final ActorContextController actorContext;
  final WorkspaceContextRepository repository;

  Future<void> close() async {
    actorContext.dispose();
    await database.close();
  }
}

Future<_Harness> _harness(MockHandler handler) async {
  const profileId = 'profile-a';
  final database = MakoloDatabase.memory();
  final store = ProfileStore(database, profileId);
  final actorContext = await ActorContextController.restore(
    profileId: profileId,
    store: _ActorStore(),
  );
  final tokens = MemoryTokenStore(
    session: const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: profileId,
    ),
  );
  final sync = SyncEngine(
    api: MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      dio: MockClient(handler).dio,
      tokenStore: tokens,
    ),
    store: store,
    database: database,
    profileId: profileId,
  );
  return _Harness(
    database: database,
    store: store,
    actorContext: actorContext,
    repository: WorkspaceContextRepository(
      database: database,
      store: store,
      profileId: profileId,
      actorContext: actorContext,
      sync: sync,
    ),
  );
}

Map<String, dynamic> _now({
  required String id,
  required String slug,
  required String responsibility,
  required String marker,
}) => {
  'space': {'id': id, 'slug': slug, 'name': id},
  'archetype': 'generic',
  'primary_business_label': 'Activités',
  'authority': {'scope': 'space', 'limited_to_activities': false},
  'responsibility': responsibility,
  'selection': {'state': 'unavailable', 'reason': 'no_safe_selection_contract'},
  'items': <Object>[],
  'has_more': false,
  'links': <String, Object?>{},
  'capabilities': <String, Object?>{},
  'marker': marker,
};

void main() {
  test('late Space A refresh is stored for A and cannot replace Space B', () async {
    final aStarted = Completer<void>();
    final aResponse = Completer<MockResponse>();
    final harness = await _harness((request) async {
      if (request.url.path.contains('/space-a/')) {
        if (!aStarted.isCompleted) aStarted.complete();
        return aResponse.future;
      }
      if (request.url.path.contains('/space-b/')) {
        return MockResponse(
          jsonEncode(
            _now(
              id: 'space-b',
              slug: 'space-b',
              responsibility: 'all',
              marker: 'B',
            ),
          ),
          200,
        );
      }
      throw StateError('Unexpected route ${request.url}');
    });
    addTearDown(harness.close);

    final spaceA = SpaceActorIdentity(id: 'space-a', slug: 'space-a');
    final spaceB = SpaceActorIdentity(id: 'space-b', slug: 'space-b');
    const all = ActorPerspective.all();

    final refreshA = harness.repository.refreshNow(spaceA, all);
    await aStarted.future;

    await harness.repository.refreshNow(spaceB, all);
    expect(
      (await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(spaceB.id, perspective: all),
      ))?.payload['marker'],
      'B',
    );

    aResponse.complete(
      MockResponse(
        jsonEncode(
          _now(
            id: 'space-a',
            slug: 'space-a',
            responsibility: 'all',
            marker: 'A-late',
          ),
        ),
        200,
      ),
    );
    await refreshA;

    expect(
      (await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(spaceA.id, perspective: all),
      ))?.payload['marker'],
      'A-late',
    );
    expect(
      (await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(spaceB.id, perspective: all),
      ))?.payload['marker'],
      'B',
    );
  });

  test('late all-perspective response cannot replace finance perspective', () async {
    final allStarted = Completer<void>();
    final allResponse = Completer<MockResponse>();
    final harness = await _harness((request) async {
      final responsibility = request.url.queryParameters['responsibility'];
      if (responsibility == null) {
        if (!allStarted.isCompleted) allStarted.complete();
        return allResponse.future;
      }
      expect(responsibility, 'finance');
      return MockResponse(
        jsonEncode(
          _now(
            id: 'space-a',
            slug: 'space-a',
            responsibility: 'finance',
            marker: 'finance',
          ),
        ),
        200,
      );
    });
    addTearDown(harness.close);

    final space = SpaceActorIdentity(id: 'space-a', slug: 'space-a');
    const all = ActorPerspective.all();
    final finance = ActorPerspective.opaque('finance');

    final refreshAll = harness.repository.refreshNow(space, all);
    await allStarted.future;
    await harness.repository.refreshNow(space, finance);

    allResponse.complete(
      MockResponse(
        jsonEncode(
          _now(
            id: 'space-a',
            slug: 'space-a',
            responsibility: 'all',
            marker: 'all-late',
          ),
        ),
        200,
      ),
    );
    await refreshAll;

    expect(
      (await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(space.id, perspective: all),
      ))?.payload['marker'],
      'all-late',
    );
    expect(
      (await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(space.id, perspective: finance),
      ))?.payload['marker'],
      'finance',
    );
  });
}
