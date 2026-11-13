import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/navigation/actor_selector.dart';
import 'package:makolo_mobile/features/space/space_occurrence_repository.dart';
import 'package:makolo_mobile/features/space/space_create_screen.dart';
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
  'links': {'workspace': '/api/v1/organizations/workspaces/$slug/'},
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
  'links': {'workspace': '/api/v1/organizations/workspaces/$slug/'},
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
  ..._contextPayload(id: id, slug: slug, responsibility: responsibility),
  'selection': {'state': 'unavailable', 'reason': 'no_safe_selection_contract'},
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
  'presentation': {
    'empty_message': 'Aucune activité visible pour le moment.',
    'section_order': [
      'preparation',
      'upcoming',
      'active',
      'blocked',
      'activities',
      'completed',
    ],
  },
  'operational_footprint': {'signals': <Object>[]},
  'sections': {
    for (final key in const [
      'preparation',
      'upcoming',
      'active',
      'blocked',
      'activities',
      'completed',
    ])
      key: {
        'representation': key == 'activities' ? 'Toutes les activités' : key,
        'role': key == 'activities' ? 'structure' : 'continuity',
        'empty_message': 'Aucun élément visible.',
        'items': <Object>[],
        'has_more': false,
        'links': <String, Object?>{},
      },
  },
  'links': {'workspace': '/api/v1/organizations/workspaces/space-x/'},
  'capabilities': {'create_activity': false},
  'marker': marker,
};

void main() {
  test('Space source keys keep actor scope', () async {
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
      SyncActorScope.space(spaceId: 'space-x', perspectiveKey: 'mandate:a/b'),
    );
    expect(oldAll.path, isNot(contains('responsibility=')));
    expect(scoped.path, contains('responsibility=mandate%3Aa%2Fb'));
  });

  test('Nous Resources summary is local-first and owner-revocable', () async {
    var phase = 'online';
    final harness = await _harness(
      handler: (request) async {
        expect(
          request.url.path,
          '/api/v1/organizations/workspaces/space-x/us/resources/',
        );
        expect(request.url.queryParameters['kind'], 'document');
        expect(request.url.queryParameters['offset'], '0');
        if (phase == 'offline') {
          throw const SocketException('offline');
        }
        if (phase == 'denied') {
          return MockResponse(
            jsonEncode({
              'error': {
                'code': 'permission_denied',
                'message': 'Access revoked',
              },
            }),
            403,
          );
        }
        return MockResponse(
          jsonEncode({
            'space_id': 'space-x',
            'visibility': 'visible',
            'kind': 'document',
            'count': 2,
            'counts': {'document': 2, 'passport': 1, 'template': 1, 'theme': 0},
            'total_count': 4,
            'items': <Object>[],
            'has_more': false,
            'next_offset': 0,
            'coverage': {
              'state': 'partial',
              'owners': [
                'space_assets.documents',
                'sharing.passport',
                'presentations.library',
              ],
            },
          }),
          200,
        );
      },
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    final source = repository.resourcesSource(space);

    expect(source.actorScope, SyncActorScope.space(spaceId: 'space-x'));
    await repository.refreshResources(space);
    final acquired = await repository.readResources(space);
    expect(acquired, isNotNull);
    expect((acquired!.payload['counts'] as Map)['document'], 2);

    phase = 'offline';
    await repository.refreshResources(space);
    expect(
      await repository.readResources(space),
      isNotNull,
      reason: 'Transport failure keeps the last acquired Resource summary.',
    );
    expect((await repository.readSource(source)).lastErrorCode, isNotNull);

    phase = 'denied';
    await repository.refreshResources(space);
    expect(
      await repository.readResources(space),
      isNull,
      reason: 'Owner denial withdraws the cached Resource summary.',
    );
    expect((await repository.readSource(source)).invalidated, isTrue);
  });

  test(
    'Space documents are local-first and scoped to the active Space',
    () async {
      var phase = 'online';
      final harness = await _harness(
        handler: (request) async {
          expect(
            request.url.path,
            '/api/v1/organizations/workspaces/space-x/documents/',
          );
          expect(request.url.queryParameters['q'], 'statuts');
          if (phase == 'offline') {
            throw const SocketException('offline');
          }
          if (phase == 'denied') {
            return MockResponse(
              jsonEncode({
                'error': {
                  'code': 'permission_denied',
                  'message': 'Access revoked',
                },
              }),
              403,
            );
          }
          return MockResponse(
            jsonEncode({
              'space_id': 'space-x',
              'count': 1,
              'items': [
                {
                  'id': '00000000-0000-4000-8000-000000000001',
                  'title': 'Statuts',
                  'visibility': 'restricted',
                  'latest_version': 1,
                },
              ],
              'has_more': false,
              'next_offset': 1,
              'can_manage': true,
            }),
            200,
          );
        },
      );
      addTearDown(harness.close);
      final repository = harness.repository;
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      final other = SpaceActorIdentity(id: 'space-y', slug: 'space-y');

      final source = repository.documentsSource(
        space,
        query: 'statuts',
        offset: 0,
      );
      expect(source.actorScope, SyncActorScope.space(spaceId: 'space-x'));
      expect(
        source.sourceKey,
        isNot(
          repository
              .documentsSource(other, query: 'statuts', offset: 0)
              .sourceKey,
        ),
      );

      await repository.refreshDocumentPage(space, query: 'statuts', offset: 0);
      final acquired = await repository.readDocumentPage(
        space,
        query: 'statuts',
        offset: 0,
      );
      expect(acquired, isNotNull);
      expect(acquired!.payload['count'], 1);
      expect(acquired.payload['_query'], 'statuts');

      phase = 'offline';
      await repository.refreshDocumentPage(space, query: 'statuts', offset: 0);
      expect(
        await repository.readDocumentPage(space, query: 'statuts', offset: 0),
        isNotNull,
        reason: 'Transport failure keeps the acquired reading snapshot.',
      );
      expect((await repository.readSource(source)).lastErrorCode, isNotNull);

      phase = 'denied';
      await repository.refreshDocumentPage(space, query: 'statuts', offset: 0);
      expect(
        await repository.readDocumentPage(space, query: 'statuts', offset: 0),
        isNull,
        reason: 'Owner denial withdraws the cached collection page.',
      );
      expect((await repository.readSource(source)).invalidated, isTrue);
    },
  );

  test('acquired Space stays locally selectable on outage but never after revocation', () async {
    var phase = 'online';
    final harness = await _harness(
      handler: (request) async {
        if (phase == 'offline') {
          throw const SocketException('offline');
        }
        if (phase == 'revoked') {
          return MockResponse(
            jsonEncode({
              'error': {
                'code': 'permission_denied',
                'message': 'Access revoked',
              },
            }),
            403,
          );
        }
        if (request.url.path.endsWith('/space-x/')) {
          return MockResponse(jsonEncode(_workspace()), 200);
        }
        return MockResponse(jsonEncode([_inventoryRow()]), 200);
      },
    );
    addTearDown(harness.close);
    final repository = harness.repository;
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    final unknown = SpaceActorIdentity(id: 'unknown', slug: 'unknown');
    expect(await repository.hasAcquiredSpaceContext(space), isFalse);
    await repository.refreshInventory();
    // Inventory-known Spaces may open before the first workspace fetch.
    expect(await repository.hasAcquiredSpaceContext(space), isTrue);
    await repository.refreshWorkspace(space);
    expect(await repository.hasAcquiredSpaceContext(space), isTrue);
    expect(await repository.hasAcquiredSpaceContext(unknown), isFalse);

    phase = 'offline';
    await expectLater(repository.refreshInventory(), throwsA(isA<Exception>()));
    await expectLater(
      repository.refreshWorkspace(space),
      throwsA(isA<Exception>()),
    );
    expect(await repository.hasAcquiredSpaceContext(space), isTrue);

    phase = 'revoked';
    await expectLater(
      repository.refreshWorkspace(space),
      throwsA(isA<Exception>()),
    );
    expect(await repository.hasAcquiredSpaceContext(space), isFalse);
  });

  test('Space context uses the current Profile local inventory only', () async {
    final harness = await _harness(
      handler: (request) async {
        if (request.url.path.endsWith('/space-x/')) {
          return MockResponse(jsonEncode(_workspace()), 200);
        }
        return MockResponse(jsonEncode([_inventoryRow()]), 200);
      },
    );
    addTearDown(harness.close);
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    await harness.repository.refreshInventory();
    await harness.repository.refreshWorkspace(space);

    final otherStore = ProfileStore(harness.database, 'profile-b');
    final otherActor = await ActorContextController.restore(
      profileId: 'profile-b',
      store: _ActorStore(),
    );
    addTearDown(otherActor.dispose);
    final otherRepository = WorkspaceContextRepository(
      database: harness.database,
      store: otherStore,
      profileId: 'profile-b',
      actorContext: otherActor,
    );
    expect(await otherRepository.hasAcquiredSpaceContext(space), isFalse);
    expect(await harness.repository.hasAcquiredSpaceContext(space), isTrue);
  });

  test('Space projections parse into local snapshots', () async {
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
              'team': {
                'items': <Object>[],
                'has_more': false,
                'links': <String, Object?>{},
              },
              'responsibilities': {
                'items': <Object>[],
                'links': <String, Object?>{},
              },
              'ownership': {
                'items': <Object>[],
                'has_more': false,
                'links': <String, Object?>{},
              },
              'trust': {'verified': false, 'claims': <Object>[]},
              'organization': {'operating_preset': <String, Object?>{}},
              'authority': {'scope': 'space', 'limited_to_activities': false},
              'links': {
                'workspace': '/api/v1/organizations/workspaces/space-x/',
              },
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
              'links': {
                'workspace': '/api/v1/organizations/workspaces/space-x/',
              },
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
              'links': {
                'workspace': '/api/v1/organizations/workspaces/space-x/',
              },
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
        resourceKey: SpaceSyncKeys.resourceKey(space.id, perspective: mandate),
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

  test('invalid payload and offline preserve snapshots', () async {
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

  test('inventory revalidates context safely', () async {
    var mode = 'renamed';
    final harness = await _harness(
      handler: (_) async {
        if (mode == 'offline') {
          throw const SocketException('offline');
        }
        if (mode == 'revoked') {
          return MockResponse(jsonEncode(<Object>[]), 200);
        }
        return MockResponse(jsonEncode([_inventoryRow(slug: 'new-slug')]), 200);
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

    expect(harness.actorContext.value, SpaceActorContext(space: space));
  });

  test(
    'workspace denial removes only its Space, actor and late responses',
    () async {
      var denyWorkspace = false;
      final lateStarted = Completer<void>();
      final lateResponse = Completer<MockResponse>();
      var delayNow = false;
      final spaceX = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      final spaceY = SpaceActorIdentity(id: 'space-y', slug: 'space-y');
      final harness = await _harness(
        handler: (request) async {
          final path = request.url.path;
          if (path == '/api/v1/organizations/workspaces/') {
            return MockResponse(
              jsonEncode([
                _inventoryRow(),
                _inventoryRow(id: 'space-y', slug: 'space-y'),
              ]),
              200,
            );
          }
          if (path == '/api/v1/organizations/workspaces/space-x/' ||
              path == '/api/v1/organizations/workspaces/space-y/') {
            if (denyWorkspace && path.contains('space-x')) {
              return MockResponse(
                jsonEncode({
                  'error': {
                    'code': 'permission_denied',
                    'message': 'Forbidden',
                  },
                }),
                403,
              );
            }
            return MockResponse(
              jsonEncode(
                _workspace(
                  id: path.contains('space-y') ? 'space-y' : 'space-x',
                  slug: path.contains('space-y') ? 'space-y' : 'space-x',
                ),
              ),
              200,
            );
          }
          if (path.endsWith('/now/')) {
            if (delayNow && path.contains('space-x')) {
              if (!lateStarted.isCompleted) lateStarted.complete();
              return lateResponse.future;
            }
            return MockResponse(
              jsonEncode(
                _now(
                  id: path.contains('space-y') ? 'space-y' : 'space-x',
                  slug: path.contains('space-y') ? 'space-y' : 'space-x',
                ),
              ),
              200,
            );
          }
          throw StateError('Unexpected route $path');
        },
      );
      addTearDown(harness.close);
      final repository = harness.repository;
      await repository.refreshInventory();
      await repository.refreshWorkspace(spaceX);
      await repository.refreshWorkspace(spaceY);
      await repository.refreshNow(spaceX, const ActorPerspective.all());
      await repository.refreshNow(spaceY, const ActorPerspective.all());
      final operational = SpaceOccurrenceRepository(
        database: harness.database,
        store: harness.store,
        profileId: 'profile-a',
        sync: repository.sync,
      );
      await harness.store.putProjection(
        kind: SpaceOccurrenceRepository.liveProjection,
        resourceKey: operational.resourceKey(spaceX, 'occ-1'),
        schemaVersion: 1,
        payload: {'state': 'stale'},
      );
      await harness.actorContext.selectSpace(spaceX);

      delayNow = true;
      final inFlight = repository.sync!.pullSource(
        repository.nowSource(spaceX, const ActorPerspective.all()),
      );
      await lateStarted.future;
      denyWorkspace = true;
      await expectLater(
        repository.refreshWorkspace(spaceX),
        throwsA(isA<Exception>()),
      );
      expect(harness.actorContext.value, const PersonalActorContext());
      expect(await repository.readWorkspace(spaceX), isNull);
      expect(await repository.readWorkspace(spaceY), isNotNull);
      expect(
        await harness.store.readProjection(
          SpaceOccurrenceRepository.liveProjection,
          resourceKey: operational.resourceKey(spaceX, 'occ-1'),
        ),
        isNull,
      );
      expect(
        (await repository.readInventory()).map((space) => space.identity.id),
        ['space-y'],
      );

      // A later inventory 200 may know the Space exists as membership, but
      // cannot regrant previously denied workspace authority.
      await repository.refreshInventory();
      expect(
        (await repository.readInventory()).map((space) => space.identity.id),
        ['space-y'],
      );

      lateResponse.complete(MockResponse(jsonEncode(_now()), 200));
      await inFlight;
      expect(
        await harness.store.readProjection(
          SpaceProjectionKind.now.wireValue,
          resourceKey: SpaceSyncKeys.resourceKey(
            spaceX.id,
            perspective: const ActorPerspective.all(),
          ),
        ),
        isNull,
      );
      await expectLater(
        repository.sync!.pullSource(
          repository.nowSource(spaceX, const ActorPerspective.all()),
        ),
        throwsA(isA<Exception>()),
      );
      await repository.sync!.invalidate(repository.workspaceSource(spaceX));
      await expectLater(
        repository.sync!.pullSource(
          repository.nowSource(spaceX, const ActorPerspective.all()),
        ),
        throwsA(isA<Exception>()),
      );
      expect(
        await harness.store.readProjection(
          SpaceProjectionKind.now.wireValue,
          resourceKey: SpaceSyncKeys.resourceKey(
            spaceY.id,
            perspective: const ActorPerspective.all(),
          ),
        ),
        isNotNull,
      );
    },
  );

  test(
    'late owner denial from a closed runtime cannot reset actor context',
    () async {
      final started = Completer<void>();
      final delayed = Completer<MockResponse>();
      final harness = await _harness(
        handler: (_) async {
          if (!started.isCompleted) started.complete();
          return delayed.future;
        },
      );
      addTearDown(harness.close);
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      await harness.actorContext.selectSpace(space);
      final pending = harness.repository.refreshWorkspace(space);
      await started.future;
      harness.repository.sync!.deactivate();
      delayed.complete(
        MockResponse(
          jsonEncode({
            'error': {'code': 'permission_denied', 'message': 'Forbidden'},
          }),
          403,
        ),
      );
      await expectLater(pending, throwsA(isA<Exception>()));
      expect(
        harness.actorContext.value,
        SpaceActorContext(space: space),
        reason: 'Only the active runtime may alter its actor preference',
      );
    },
  );

  test(
    'owner inventory removal withdraws one Space without global erasure',
    () async {
      var includeX = true;
      final x = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      final y = SpaceActorIdentity(id: 'space-y', slug: 'space-y');
      final harness = await _harness(
        handler: (request) async {
          final path = request.url.path;
          if (path == '/api/v1/organizations/workspaces/') {
            return MockResponse(
              jsonEncode([
                if (includeX) _inventoryRow(),
                _inventoryRow(id: 'space-y', slug: 'space-y'),
              ]),
              200,
            );
          }
          if (path.endsWith('/space-x/')) {
            return MockResponse(jsonEncode(_workspace()), 200);
          }
          if (path.endsWith('/space-y/')) {
            return MockResponse(
              jsonEncode(_workspace(id: 'space-y', slug: 'space-y')),
              200,
            );
          }
          throw StateError('Unexpected path $path');
        },
      );
      addTearDown(harness.close);
      final repo = harness.repository;
      await repo.refreshInventory();
      await repo.refreshWorkspace(x);
      await repo.refreshWorkspace(y);
      includeX = false;
      await repo.refreshInventory();
      expect(await repo.readWorkspace(x), isNull);
      expect(await repo.readWorkspace(y), isNotNull);
      expect((await repo.readInventory()).map((item) => item.identity.id), [
        'space-y',
      ]);
      expect(
        (await repo.readSource(repo.workspaceSource(x))).invalidated,
        true,
      );
    },
  );

  test(
    'transport failure cannot erase a Workspace authority tombstone',
    () async {
      var denied = true;
      final harness = await _harness(
        handler: (_) async => MockResponse(
          jsonEncode({
            'error': {
              'code': denied ? 'permission_denied' : 'server_unavailable',
              'message': 'Unable to verify Workspace',
            },
          }),
          denied ? 403 : 503,
        ),
      );
      addTearDown(harness.close);
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      await expectLater(
        harness.repository.refreshWorkspace(space),
        throwsA(isA<Exception>()),
      );
      denied = false;
      await expectLater(
        harness.repository.refreshWorkspace(space),
        throwsA(isA<Exception>()),
      );
      final source = await harness.repository.readSource(
        harness.repository.workspaceSource(space),
      );
      expect(source.invalidated, isTrue);
      expect(source.lastErrorCode, 'permission_denied');
      await expectLater(
        harness.repository.sync!.pullSource(
          harness.repository.nowSource(space, const ActorPerspective.all()),
        ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test(
    'inventory 403 withdraws all Space projections but no other Profile',
    () async {
      var deny = false;
      final harness = await _harness(
        handler: (request) async {
          if (deny) {
            return MockResponse(
              jsonEncode({
                'error': {'code': 'permission_denied', 'message': 'Forbidden'},
              }),
              403,
            );
          }
          if (request.url.path.endsWith('/space-x/')) {
            return MockResponse(jsonEncode(_workspace()), 200);
          }
          return MockResponse(jsonEncode([_inventoryRow()]), 200);
        },
      );
      addTearDown(harness.close);
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      await harness.repository.refreshInventory();
      await harness.repository.refreshWorkspace(space);
      await harness.actorContext.selectSpace(space);
      final another = ProfileStore(harness.database, 'profile-b');
      await another.putProjection(
        kind: SpaceProjectionKind.workspace.wireValue,
        resourceKey: 'space-x',
        schemaVersion: 1,
        payload: {'profile': 'B'},
      );
      deny = true;
      await expectLater(
        harness.repository.refreshInventory(),
        throwsA(isA<Exception>()),
      );
      expect(harness.actorContext.value, const PersonalActorContext());
      expect(await harness.repository.readWorkspace(space), isNull);
      expect(await harness.repository.readInventory(), isEmpty);
      expect(
        (await another.readProjection(
          SpaceProjectionKind.workspace.wireValue,
          resourceKey: 'space-x',
        ))?.payload['profile'],
        'B',
      );
    },
  );

  test('Profile isolation keeps Space snapshots separate', () async {
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

  test(
    'native Space creation uses the owner without granting client authority',
    () async {
      var posted = false;
      final harness = await _harness(
        handler: (request) async {
          if (request.url.path == '/api/v1/organizations/workspaces/' &&
              request.data != null) {
            final payload = request.data as Map;
            expect(payload['name'], 'Association Lumière');
            expect(payload['public_profile'], false);
            posted = true;
            return MockResponse(jsonEncode(_workspace()), 201);
          }
          throw StateError('Unexpected request: ${request.url.path}');
        },
      );
      addTearDown(harness.close);

      final identity = await harness.repository.createSpace(
        name: ' Association Lumière ',
        publicProfile: false,
      );
      expect(posted, isTrue);
      expect(identity, SpaceActorIdentity(id: 'space-x', slug: 'space-x'));
      expect(harness.actorContext.value, const PersonalActorContext());
    },
  );

  testWidgets(
    'actor picker opens an inventory-known Space without first workspace data',
    (tester) async {
      var offline = false;
      var requests = 0;
      final harness = await _harness(
        handler: (request) async {
          requests++;
          if (offline) throw const SocketException('offline');
          if (request.url.path.endsWith('/space-x/')) {
            fail('Workspace must not be a prerequisite to choose the context');
          }
          return MockResponse(jsonEncode([_inventoryRow()]), 200);
        },
      );
      addTearDown(harness.close);
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      await harness.repository.refreshInventory();
      offline = true;
      final beforeSelection = requests;
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
        actorContext: harness.actorContext,
        space: harness.repository,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () =>
                    showMakoloActorPicker(context, runtime: runtime),
                child: const Text('Choisir un contexte'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choisir un contexte'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Space X'));
      await tester.pumpAndSettle();
      expect(harness.actorContext.value, SpaceActorContext(space: space));
      expect(requests, beforeSelection);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets(
    'actor picker switches to an acquired Space without the server or network chatter',
    (tester) async {
      var offline = false;
      var requests = 0;
      final harness = await _harness(
        handler: (request) async {
          requests++;
          if (offline) throw const SocketException('offline');
          if (request.url.path.endsWith('/space-x/')) {
            return MockResponse(jsonEncode(_workspace()), 200);
          }
          return MockResponse(jsonEncode([_inventoryRow()]), 200);
        },
      );
      addTearDown(harness.close);
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      await harness.repository.refreshInventory();
      await harness.repository.refreshWorkspace(space);
      offline = true;
      await expectLater(
        harness.repository.refreshInventory(),
        throwsA(isA<Exception>()),
      );
      final baseline = requests;
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
        actorContext: harness.actorContext,
        space: harness.repository,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () =>
                    showMakoloActorPicker(context, runtime: runtime),
                child: const Text('Choisir un contexte'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choisir un contexte'));
      await tester.pumpAndSettle();
      expect(find.text('Space X'), findsOneWidget);
      expect(find.text('Vérifier mes Espaces'), findsNothing);
      expect(find.textContaining('Espaces déjà consultés'), findsNothing);
      expect(find.textContaining('ne peuvent pas être vérifiés'), findsNothing);
      await tester.tap(find.text('Space X'));
      await tester.pumpAndSettle();
      expect(harness.actorContext.value, SpaceActorContext(space: space));
      expect(requests, baseline);
      expect(find.text('Agir en tant que'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets(
    'uncertain create response cannot repeat an unconfirmed Space POST',
    (tester) async {
      var attempts = 0;
      final harness = await _harness(
        handler: (request) async {
          if (request.url.path == '/api/v1/organizations/workspaces/' &&
              request.data != null) {
            attempts++;
            return const MockResponse(
              '{"error":{"code":"unavailable","message":"Try later"}}',
              503,
            );
          }
          throw StateError('Unexpected request');
        },
      );
      addTearDown(harness.close);
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
        actorContext: harness.actorContext,
        space: harness.repository,
      );

      await tester.pumpWidget(
        MaterialApp(home: SpaceCreateScreen(runtime: runtime)),
      );
      expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
        isTrue,
      );
      await tester.enterText(find.byType(TextFormField), 'Espace Associatif');
      await tester.tap(find.text('Créer cet Espace'));
      await tester.pumpAndSettle();

      expect(attempts, 1);
      expect(find.textContaining('Réponse incertaine'), findsOneWidget);
      final submit = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(submit.onPressed, isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
