import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_wire.dart';

Map<String, dynamic> spaceEnvelope({String actorId = 'space-a', String viewerId = 'profile-1'}) => {
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
    expect(parsed.copyWith(spaceId: 'space-a').mapFingerprint, a.mapFingerprint);
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
        spaceEnvelope(), scope: 'space', expectedSpaceId: 'space-b',
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
        untrusted, scope: 'space', expectedSpaceId: 'space-a',
      ),
      throwsFormatException,
    );
  });

  test('Space shell reuses canonical N1 and generic search/map routes', () {
    final shell = File('lib/features/space/space_shell_routes.dart').readAsStringSync();
    final routes = File('lib/features/discovery/discovery_routes.dart').readAsStringSync();
    final screens = File('lib/features/discovery/discovery_screens.dart').readAsStringSync();
    expect(shell, contains('return DiscoveryScreen('));
    expect(shell, contains('initialQuery: query'));
    expect(routes, contains('DiscoverySearchScreen('));
    expect(routes, contains('DiscoveryMapScreen('));
    expect(routes, contains('actor.space.slug != query.spaceSlug'));
    expect(screens, contains('if (current.isSpace) return null;'));
  });
}
