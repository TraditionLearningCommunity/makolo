import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_wire.dart';

Map<String, dynamic> spaceEnvelope({
  String actorId = 'space-a',
  String viewerId = 'profile-1',
}) => {
  'meta': {
    'projection': 'discovery.items',
    'schema_version': 1,
    'scope': 'space',
    'generated_at': '2026-11-09T08:00:00+00:00',
  },
  'data': {
    'surface': 'discover_space',
    'actor': {'type': 'space', 'id': actorId},
    'viewer': {'type': 'profile', 'id': viewerId},
    'results': <Object>[],
    'items': <Object>[],
    'count': 0,
    'page': 1,
    'page_size': 24,
    'has_next': false,
    'selection': {'state': 'empty'},
    'terminal': {'state': 'empty'},
    'continuation': {'state': 'end', 'token': null},
    'exploration': <String, Object>{},
    'freshness': <String, Object>{},
  },
};

void main() {
  test('Space uses same Discovery query and map paths, separated by actor', () {
    const personal = DiscoveryQuery(text: 'festival');
    const a = DiscoveryQuery(
      text: 'festival',
      spaceSlug: 'atelier',
      spaceId: 'space-a',
    );
    const b = DiscoveryQuery(
      text: 'festival',
      spaceSlug: 'atelier',
      spaceId: 'space-b',
    );
    expect(personal.path, contains('api/v1/discovery/items/'));
    expect(a.path, contains('api/v1/discovery/items/'));
    expect(a.path, contains('context=space'));
    expect(a.mapPath, contains('api/v1/discovery/map/'));
    expect(a.mapPath, contains('space=atelier'));
    expect(a.fingerprint, isNot(personal.fingerprint));
    expect(a.fingerprint, isNot(b.fingerprint));
    expect(a.mapFingerprint, isNot(b.mapFingerprint));
    expect(a.copyWith(text: 'concert').spaceId, 'space-a');
    final route = a.routeLocation('/discover/map');
    final parsed = DiscoveryQuery.fromRouteParameters(
      Uri.parse(route).queryParameters,
    );
    expect(parsed.spaceSlug, 'atelier');
    expect(parsed.text, 'festival');
    expect(
      parsed.copyWith(spaceId: 'space-a').mapFingerprint,
      a.mapFingerprint,
    );
    expect(a.watchCriteria, personal.watchCriteria);
  });

  test('untrusted Space actor parameters are rejected', () {
    for (final params in [
      {'context': 'space'},
      {'space': 'atelier'},
      {'context': 'wrong', 'space': 'atelier'},
    ]) {
      expect(
        () => DiscoveryQuery.fromRouteParameters(params),
        throwsFormatException,
      );
    }
  });

  test('Space wire requires the exact server Space and a Profile viewer', () {
    final wire = DiscoveryWire.receive(
      spaceEnvelope(),
      scope: 'space',
      expectedSpaceId: 'space-a',
    );
    expect(wire.data['surface'], 'discover_space');
    expect(
      () => DiscoveryWire.receive(
        spaceEnvelope(),
        scope: 'space',
        expectedSpaceId: 'space-b',
      ),
      throwsFormatException,
    );
    expect(
      () => DiscoveryWire.receive(spaceEnvelope(), scope: 'personal'),
      throwsFormatException,
    );
    final untrusted = spaceEnvelope();
    (untrusted['data'] as Map)['viewer'] = null;
    expect(
      () => DiscoveryWire.receive(
        untrusted,
        scope: 'space',
        expectedSpaceId: 'space-a',
      ),
      throwsFormatException,
    );
  });

  test('N3 Space wire verifies the real actor and viewer before caching', () {
    final envelope = <String, dynamic>{
      'meta': {
        'projection': 'discovery.item',
        'schema_version': 1,
        'scope': 'space',
        'generated_at': '2026-11-09T08:00:00+00:00',
      },
      'data': {
        'actor': {'type': 'space', 'id': 'space-a'},
        'viewer': {'type': 'profile', 'id': 'profile-1'},
        'item': {
          'identity': {
            'family': 'activity',
            'candidate_key': 'activity:one',
            'resource': {'kind': 'activity', 'id': 'one'},
          },
          'representation': {'title': 'Possibilité publique'},
          'capabilities': ['view'],
        },
      },
    };
    final verified = DiscoveryWire.receiveItem(
      envelope,
      scope: 'space',
      expectedSpaceId: 'space-a',
      expectedViewerId: 'profile-1',
    );
    expect(
      (verified['representation'] as Map)['title'],
      'Possibilité publique',
    );
    expect(
      () => DiscoveryWire.receiveItem(
        envelope,
        scope: 'space',
        expectedSpaceId: 'space-b',
        expectedViewerId: 'profile-1',
      ),
      throwsFormatException,
    );
    expect(
      () => DiscoveryWire.receiveItem(
        envelope,
        scope: 'space',
        expectedSpaceId: 'space-a',
        expectedViewerId: 'other-viewer',
      ),
      throwsFormatException,
    );
    expect(
      () => DiscoveryWire.receiveItem(envelope, scope: 'personal'),
      throwsFormatException,
    );
  });

  test('N3 has one route and one detail widget across actor contexts', () {
    final routes = File('lib/features/discovery/discovery_routes.dart')
        .readAsStringSync();
    final screens = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final unit = File(
      'lib/presentation/possibilities/discovery_possibility_unit.dart',
    ).readAsStringSync();
    final repository = File('lib/features/discovery/discovery_repository.dart')
        .readAsStringSync();
    expect(routes, contains("path: '/discover/items/:family/:id'"));
    expect(routes, contains('actorQuery: actorQuery'));
    expect(routes, contains('DiscoveryItemDetailScreen('));
    expect(screens, contains("Key('discover-n3-resume-journey')"));
    expect(screens, contains('collectiveReadOnly: widget.actorQuery.isSpace'));
    expect(unit, contains('widget.collectiveReadOnly'));
    expect(repository, contains(r"sourceKey: 'discovery-item:$resourceKey'"));
    expect(repository, contains("page.payload['surface'] != 'discover_space'"));
  });

  test(
    'a Space route keeps actor identity through list/map/search and page',
    () {
      const actor = DiscoveryQuery(
        spaceSlug: 'atelier',
        spaceId: 'space-a',
        text: 'atelier',
        place: 'Kinshasa',
        pageSize: 2,
      );
      final next = actor.copyWith(
        page: 2,
        continuation: 'opaque-signed-cursor',
      );
      expect(next.isSpace, isTrue);
      expect(next.parameters['space'], 'atelier');
      expect(next.parameters['continuation'], 'opaque-signed-cursor');
      expect(next.fingerprint, isNot(actor.fingerprint));
      expect(next.mapFingerprint, actor.mapFingerprint);
      for (final path in ['/discover/search', '/discover/map']) {
        final route = Uri.parse(next.routeLocation(path));
        expect(route.queryParameters['context'], 'space');
        expect(route.queryParameters['space'], 'atelier');
        expect(route.queryParameters['page'], '2');
        final restored = DiscoveryQuery.fromRouteParameters(
          route.queryParameters,
        ).copyWith(spaceId: actor.spaceId);
        expect(restored.fingerprint, next.fingerprint);
      }
      expect(
        next
            .copyWith(text: 'festival', page: 1, clearContinuation: true)
            .spaceId,
        'space-a',
      );
      expect(next.watchCriteria, isNot(contains('context')));
      expect(next.watchCriteria, isNot(contains('continuation')));
    },
  );

  test('actor guard and read-only map controls survive route changes', () {
    final appRouter = File('lib/app/router.dart').readAsStringSync();
    final discoveryRoutes = File('lib/features/discovery/discovery_routes.dart')
        .readAsStringSync();
    final screens = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final map = File('lib/features/discovery/discovery_mature_view.dart')
        .readAsStringSync();
    final repository = File('lib/features/discovery/discovery_repository.dart')
        .readAsStringSync();
    expect(appRouter, contains("parameters.containsKey('context')"));
    expect(
      discoveryRoutes,
      contains('actor is SpaceActorContext ? null : query'),
    );
    expect(
      discoveryRoutes,
      contains("_contextualItemRoute('activity', id, query)"),
    );
    expect(screens, contains('collectiveReadOnly: _query.isSpace'));
    expect(map, contains('if (!collectiveReadOnly) Expanded('));
    expect(repository, contains("field['surface'] != 'discover_space'"));
    expect(repository, contains("field['surface'] != 'discover_me'"));
    expect(screens, contains('await repository.readItem('));
  });

  test('Space shell reuses canonical N1 and generic search/map routes', () {
    final shell = File('lib/features/space/space_shell_routes.dart')
        .readAsStringSync();
    final routes = File('lib/features/discovery/discovery_routes.dart')
        .readAsStringSync();
    final screens = File('lib/features/discovery/discovery_screens.dart')
        .readAsStringSync();
    final appShell = File('lib/app/app_shell.dart').readAsStringSync();
    expect(appShell, contains('enableSpaceDiscoveryActions'));
    expect(
      appShell,
      contains("discoveryQuery.routeLocation('/discover/search')"),
    );
    expect(appShell, contains("discoveryQuery.routeLocation('/discover/map')"));
    expect(shell, contains('return DiscoveryScreen('));
    expect(shell, contains('initialQuery: query'));
    expect(routes, contains('DiscoverySearchScreen('));
    expect(routes, contains('DiscoveryMapScreen('));
    expect(routes, contains('actor.space.slug != query.spaceSlug'));
    expect(screens, contains('if (current.isSpace) return null;'));
  });
}
