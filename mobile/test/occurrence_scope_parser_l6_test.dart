import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_source.dart';

Map<String, dynamic> _envelope({
  String occurrence = 'occ-a',
  String viewer = 'profile-a',
  String? space,
  String surface = 'day_of',
}) => {
  'meta': {
    'projection': 'occurrence.experience.$surface',
    'schema_version': 1,
    'generated_at': '2026-11-09T11:00:00Z',
    'scope': 'occurrence',
  },
  'data': {
    'identity': {'kind': 'occurrence', 'id': occurrence},
    'context': {
      'viewer_profile_id': viewer,
      'actor_space_id': space,
      'occurrence': {'id': occurrence},
    },
    'surface': surface,
  },
};

void main() {
  final personal = SyncSourceDefinition.projectionEnvelope(
    sourceKey: 'day-of-experience:occ-a',
    owner: 'Operations',
    path: 'api/v1/operations/occurrences/occ-a/experience/day-of/',
    projectionKind: 'occurrence.experience.day_of',
    resourceKey: 'occ-a',
    expectedOccurrenceId: 'occ-a',
    expectedViewerProfileId: 'profile-a',
    expectedSurface: 'day_of',
  );

  ApiResponse response(Map<String, dynamic> body) =>
      ApiResponse(200, jsonEncode(body), const {});

  test(
    'L6: correct owner response may enter the personal projection cache',
    () {
      final acquired = personal.parser(response(_envelope()));
      expect(acquired.payload['identity']['id'], 'occ-a');
    },
  );

  test(
    'L6: wrong owner identity, Profile, Space or surface cannot be cached',
    () {
      final cases = [
        _envelope(occurrence: 'occ-b'),
        _envelope(viewer: 'profile-b'),
        _envelope(space: 'space-a'),
        _envelope(surface: 'live'),
      ];
      for (final json in cases) {
        expect(() => personal.parser(response(json)), throwsFormatException);
      }
    },
  );

  test('L6: matching Space actor is distinct from personal actor cache', () {
    final institutional = SyncSourceDefinition.projectionEnvelope(
      sourceKey: 'space-day-of:space-a:occ-a',
      owner: 'Operations',
      path: 'api/v1/operations/occurrences/occ-a/experience/day-of/?actor_space=space-a',
      projectionKind: 'occurrence.experience.day_of',
      resourceKey: 'space-a|occ-a',
      actorScope: SyncActorScope.space(spaceId: 'space-a'),
      expectedOccurrenceId: 'occ-a',
      expectedViewerProfileId: 'profile-a',
      expectedActorSpaceId: 'space-a',
      expectedSurface: 'day_of',
    );
    final acquired = institutional.parser(
      response(_envelope(space: 'space-a')),
    );
    expect(acquired.payload['context']['actor_space_id'], 'space-a');
    expect(
      () => institutional.parser(response(_envelope(space: 'space-b'))),
      throwsFormatException,
    );
    expect(
      () => institutional.parser(response(_envelope())),
      throwsFormatException,
    );
  });
}
