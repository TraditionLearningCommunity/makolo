import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/sync/sync_source.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  final Map<String, ActorContext> values = {};

  @override
  Future<ActorContext> readActorContext(String profileId) async =>
      values[profileId] ?? const PersonalActorContext();

  @override
  Future<void> writeActorContext(
    String profileId,
    ActorContext context,
  ) async {
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

Future<_Harness> _harness({
  required MockHandler handler,
  String profileId = 'profile-a',
}) async {
  final tokens = MemoryTokenStore(
    session: AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: profileId,
    ),
  );
  final database = MakoloDatabase.memory();
  final store = ProfileStore(database, profileId);
  final actorContext = await ActorContextController.restore(
    profileId: profileId,
    store: _ActorStore(),
  );
  final api = MakoloApiClient(
    baseUri: Uri.parse('https://makolo.invalid/'),
    dio: MockClient(handler).dio,
    tokenStore: tokens,
  );
  final sync = SyncEngine(
    api: api,
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

Map<String, dynamic> _inventoryRow({
  String id = 'space-x',
  String slug = 'space-x',
}) => {
  'id': id,
  'slug': slug,
  'name': 'Space X',
  'archetype': 'generic',
  'lifecycle': 'active',
  'limited_to_activities': false,
  'links': {
    'workspace': '/api/v1/organizations/workspaces/$slug/',
  },
};

Map<String, dynamic> _workspace({
  String id = 'space-x',
  String slug = 'space-x',
  List<String> perspectives = const ['all', 'mandate:a'],
}) => {
  'space': {
    'id': id,
    'slug': slug,
    'name': 'Space X',
    'description': null,
    'archetype': 'generic',
    'lifecycle': 'active',
    'public_profile': true,
  },
  'verification': {'verified': false, 'claims': <Object>[]},
  'authority': {'scope': 'space', 'limited_to_activities': false},
  'capabilities': {
    'update_space': false,
    'manage_team': false,
    'manage_ownership': false,
  },
  'operating_preset': {
    'label': 'Espace',
    'navigation_section_label': 'Activités',
    'activities_label': 'Activités',
    'primary_business_label': 'Activités',
    'featured_modules': <Object>[],
    'suggested_verticals': <Object>[],
  },
  'responsibilities': perspectives
      .map(
        (key) => {
          'key': key,
          'label': key == 'all'
              ? 'Toutes mes responsabilités'
              : 'Responsabilité A',
          'scope': 'space',
          'combined': key == 'all',
        },
      )
      .toList(),
  'links': {
    'workspace': '/api/v1/organizations/workspaces/$slug/',
  },
  'modules': <Object>[],
  'platform_modules_included': false,
};

Map<String, dynamic> _contextPayload({
  String id = 'space-x',
  String slug = 'space-x',
  String responsibility = 'all',
}) => {
  'space': {'id': id, 'slug': slug, 'name': 'Space X'},
  'archetype': 'generic',
  'primary_business_label': 'Activités',
  'authority': {'scope': 'space', 'limited_to_activities': false},
  'responsibility': responsibility,
};

Map<String, dynamic> _now({
  String id = 'space-x',
  String slug = 'space-x',
  String responsibility = 'all',
  String marker = 'valid',
}) => {
  ..._contextPayload(
    id: id,
    slug: slug,
    responsibility: responsibility,
  ),
  'selection': {
    'state': 'unavailable',
    'reason': 'no_safe_selection_contract',
  },
  'items': <Object>[],
  'has_more': false,
  'links': <String, Object?>{},
  'capabilities': <String, Object?>{},
  'marker': marker,
};

Map<String, dynamic> _work({
  String responsibility = 'all',
  String marker = 'valid',
}) => {
  ..._contextPayload(responsibility: responsibility),
  'operational_footprint': {'signals': <Object>[]},
  'sections': {
    for (final key in const [
      'preparation',
      'upcoming',
      'active',
      'blocked',
      'completed',
    ])
      key: {'items': <Object>[], 'has_more': false, 'links': <String, Object?>{}},
  },
  'links': {
    'workspace': '/api/v1/organizations/workspaces/space-x/',
  },
  'capabilities': {'create_activity': false},
  'marker': marker,
};

void main() {
  test('Space source identity is actor scoped and independent from route slug', () async {
    final harness = await _harness(
      handler: (_) async => const MockResponse('{}', 200),
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final oldSpace = SpaceActorIdentity(id: 'space-x', slug: 'old-slug');
    final renamedSpace = SpaceActorIdentity(id: 'space-x', slug: 'new-slug');
    final otherSpace = SpaceActorIdentity(id: 'space-y', slug: 'space-y');
    final all = const ActorPerspective.all();
    final mandate = ActorPerspective.opaque('mandate:a/b');

    final oldAll = repository.nowSource(oldSpace, all);
    final renamedAll = repository.nowSource(renamedSpace, all);
    final scoped = repository.nowSource(oldSpace, mandate);
    final other = repository.nowSource(otherSpace, all);

    expect(oldAll.sourceKey, renamedAll.sourceKey);
    expect(oldAll.path, isNot(renamedAll.path));
    expect(oldAll.sourceKey, isNot(scoped.sourceKey));
    expect(oldAll.sourceKey, isNot(other.sourceKey));
    expect(oldAll.resourceKey, isNot(scoped.resourceKey));
    expect(oldAll.actorScope, SyncActorScope.space(spaceId: 'space-x'));
    expect(
      scoped.actorScope,
      SyncActorScope.space(
        spaceId: 'space-x',
        perspectiveKey: 'mandate:a/b',
      ),
    );
    expect(oldAll.path, isNot(contains('responsibility=')));
    expect(scoped.path, contains('responsibility=mandate%3Aa%2Fb'));
  });

  test('all direct Space projections parse and remain locally readable', () async {
    final harness = await _harness(
      handler: (request) async {
        final path = request.url.path;
        if (path == '/api/v1/organizations/workspaces/') {
          return MockResponse(jsonEncode([_inventoryRow()]), 200);
        }
        if (path == '/api/v1/organizations/workspaces/space-x/') {
          return MockResponse(jsonEncode(_workspace()), 200);
        }
        if (path.endsWith('/now/')) {
          return MockResponse(
            jsonEncode(
              _now(
                responsibility:
                    request.url.queryParameters['responsibility'] ?? 'all',
              ),
            ),
            200,
          );
        }
        if (path.endsWith('/discover/')) {
          return MockResponse(jsonEncode(_now()), 200);
        }
        if (path.endsWith('/work/')) {
          return MockResponse(
            jsonEncode(
              _work(
                responsibility:
                    request.url.queryParameters['responsibility'] ?? 'all',
              ),
            ),
            200,
          );
        }
        if (path.endsWith('/us/')) {
          return MockResponse(
            jsonEncode({
              'identity': {
                'id': 'space-x',
                'slug': 'space-x',
                'name': 'Space X',
                'archetype': 'generic',
                'lifecycle': 'active',
                'public_profile': true,
              },
              'team': {'items': <Object>[], 'has_more': false, 'links': <String, Object?>{}},
              'responsibilities': {'items': <Object>[], 'links': <String, Object?>{}},
              'ownership': {'items': <Object>[], 'has_more': false, 'links': <String, Object?>{}},
              'trust': {'verified': false, 'claims': <Object>[]},
              'organization': {'operating_preset': <String, Object?>{}},
              'authority': {'scope': 'space', 'limited_to_activities': false},
              'links': {'workspace': '/api/v1/organizations/workspaces/space-x/'},
              'capabilities': <String, Object?>{},
            }),
            200,
          );
        }
        if (path.endsWith('/relationships/')) {
          return MockResponse(
            jsonEncode({
              'label': 'Relations',
              'authority': {'scope': 'space', 'limited_to_activities': false},
              'sections': <String, Object?>{},
              'links': {'workspace': '/api/v1/organizations/workspaces/space-x/'},
              'capabilities': <String, Object?>{},
            }),
            200,
          );
        }
        if (path.endsWith('/pilot/')) {
          return MockResponse(
            jsonEncode({
              'authority': {'scope': 'space', 'limited_to_activities': false},
              'sections': <String, Object?>{},
              'signals': <Object>[],
              'links': {'workspace': '/api/v1/organizations/workspaces/space-x/'},
              'capabilities': <String, Object?>{},
            }),
            200,
          );
        }
        throw StateError('Unexpected route $path');
      },
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    final mandate = ActorPerspective.opaque('mandate:a');

    await repository.refreshInventory();
    await repository.refreshWorkspace(space);
    await repository.refreshNow(space, const ActorPerspective.all());
    await repository.refreshNow(space, mandate);
    await repository.refreshDiscover(space);
    await repository.refreshWork(space, const ActorPerspective.all());
    await repository.refreshWork(space, mandate);
    await repository.refreshUs(space);
    await repository.refreshRelationships(space);
    await repository.refreshPilot(space);

    expect((await repository.readInventory()).single.identity, space);
    expect((await repository.readWorkspace(space))?.identity, space);
    expect(
      await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(
          space.id,
          perspective: const ActorPerspective.all(),
        ),
      ),
      isNotNull,
    );
    expect(
      await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(
          space.id,
          perspective: mandate,
        ),
      ),
      isNotNull,
    );
    for (final kind in const [
      SpaceProjectionKind.discover,
      SpaceProjectionKind.us,
      SpaceProjectionKind.relationships,
      SpaceProjectionKind.pilot,
    ]) {
      expect(
        await harness.store.readProjection(
          kind.wireValue,
          resourceKey: SpaceSyncKeys.resourceKey(space.id),
        ),
        isNotNull,
      );
    }
  });

  test('invalid payload and normal offline failure preserve last valid snapshot', () async {
    var mode = 'valid';
    final harness = await _harness(
      handler: (request) async {
        if (mode == 'offline') {
          throw const SocketException('offline');
        }
        if (request.url.path.endsWith('/now/')) {
          return MockResponse(
            jsonEncode(
              mode == 'invalid'
                  ? _now(id: 'another-space', marker: 'invalid')
                  : _now(marker: 'valid'),
            ),
            200,
          );
        }
        throw StateError('Unexpected route');
      },
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    final source = repository.nowSource(space, const ActorPerspective.all());

    await repository.refreshNow(space, const ActorPerspective.all());
    var snapshot = await harness.store.readProjection(
      SpaceProjectionKind.now.wireValue,
      resourceKey: source.resourceKey,
    );
    expect(snapshot?.payload['marker'], 'valid');

    mode = 'invalid';
    await repository.refreshNow(space, const ActorPerspective.all());
    snapshot = await harness.store.readProjection(
      SpaceProjectionKind.now.wireValue,
      resourceKey: source.resourceKey,
    );
    expect(snapshot?.payload['marker'], 'valid');

    mode = 'offline';
    await repository.refreshNow(space, const ActorPerspective.all());
    snapshot = await harness.store.readProjection(
      SpaceProjectionKind.now.wireValue,
      resourceKey: source.resourceKey,
    );
    expect(snapshot?.payload['marker'], 'valid');
    expect((await repository.readSource(source)).lastErrorCode, isNotNull);
  });

  test('404 removes only the scoped projection', () async {
    var notFound = false;
    final harness = await _harness(
      handler: (request) async {
        if (request.url.path.endsWith('/now/')) {
          if (notFound) {
            return MockResponse(
              jsonEncode({
                'error': {'code': 'not_found', 'message': 'Gone'},
              }),
              404,
            );
          }
          return MockResponse(jsonEncode(_now()), 200);
        }
        if (request.url.path.endsWith('/work/')) {
          return MockResponse(jsonEncode(_work()), 200);
        }
        throw StateError('Unexpected route');
      },
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    final all = const ActorPerspective.all();

    await repository.refreshNow(space, all);
    await repository.refreshWork(space, all);
    notFound = true;
    await repository.refreshNow(space, all);

    expect(
      await harness.store.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(space.id, perspective: all),
      ),
      isNull,
    );
    expect(
      await harness.store.readProjection(
        SpaceProjectionKind.work.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(space.id, perspective: all),
      ),
      isNotNull,
    );
  });

  test('inventory revalidates revocation and slug changes but not transport failure', () async {
    var mode = 'renamed';
    final harness = await _harness(
      handler: (_) async {
        if (mode == 'offline') {
          throw const SocketException('offline');
        }
        if (mode == 'revoked') {
          return MockResponse(jsonEncode(<Object>[]), 200);
        }
        return MockResponse(
          jsonEncode([_inventoryRow(slug: 'new-slug')]),
          200,
        );
      },
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final perspective = ActorPerspective.opaque('mandate:a');
    await harness.actorContext.selectSpace(
      SpaceActorIdentity(id: 'space-x', slug: 'old-slug'),
      perspective: perspective,
    );

    await repository.refreshInventory();
    expect(
      harness.actorContext.value,
      SpaceActorContext(
        space: SpaceActorIdentity(id: 'space-x', slug: 'new-slug'),
        perspective: perspective,
      ),
    );

    mode = 'offline';
    await expectLater(repository.refreshInventory(), throwsA(anything));
    expect(harness.actorContext.value, isA<SpaceActorContext>());

    mode = 'revoked';
    await repository.refreshInventory();
    expect(harness.actorContext.value, const PersonalActorContext());
  });

  test('workspace revalidation drops only a revoked perspective', () async {
    final harness = await _harness(
      handler: (_) async => MockResponse(
        jsonEncode(_workspace(perspectives: const ['all'])),
        200,
      ),
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    await harness.actorContext.selectSpace(
      space,
      perspective: ActorPerspective.opaque('mandate:gone'),
    );

    await repository.refreshWorkspace(space);

    expect(
      harness.actorContext.value,
      SpaceActorContext(space: space),
    );
  });

  test('ProjectionSnapshots remain Profile isolated with identical Space keys', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final a = ProfileStore(database, 'profile-a');
    final b = ProfileStore(database, 'profile-b');
    final key = SpaceSyncKeys.resourceKey(
      'space-x',
      perspective: const ActorPerspective.all(),
    );

    await a.putProjection(
      kind: SpaceProjectionKind.now.wireValue,
      resourceKey: key,
      schemaVersion: 1,
      payload: {'owner': 'A'},
    );
    await b.putProjection(
      kind: SpaceProjectionKind.now.wireValue,
      resourceKey: key,
      schemaVersion: 1,
      payload: {'owner': 'B'},
    );

    expect(
      (await a.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: key,
      ))?.payload['owner'],
      'A',
    );
    expect(
      (await b.readProjection(
        SpaceProjectionKind.now.wireValue,
        resourceKey: key,
      ))?.payload['owner'],
      'B',
    );
  });
}
