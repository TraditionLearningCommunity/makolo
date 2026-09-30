import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/preparation/preparation_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  test('PC stores Requirement owner projection as keyed local snapshot', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      expect(
        request.url.path,
        '/api/v1/me/journeys/journey-1/requirements/assessment-1/',
      );
      return MockResponse(
        jsonEncode({
          'meta': {
            'projection': 'personal.journey.requirement.detail',
            'schema_version': 1,
            'generated_at': '2026-09-30T14:30:00Z',
          },
          'data': {
            'identity': {
              'kind': 'requirement_assessment',
              'id': 'assessment-1',
              'journey_id': 'journey-1',
            },
            'requirement': {
              'kind': 'document',
              'label': 'Passeport valide',
              'required': true,
            },
            'assessment': {
              'state': 'missing',
              'consequence': 'blocking',
              'reason': null,
            },
            'ways_to_satisfy': [],
            'capabilities': [],
            'links': {'journey': '/api/v1/me/journeys/journey-1/'},
          },
        }),
        200,
      );
    });
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: client.dio,
    );
    final sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    final repository = RequirementRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await repository.refresh(
      journeyId: 'journey-1',
      assessmentId: 'assessment-1',
    );

    final stored = await repository.readDetail('assessment-1');
    expect(stored, isNotNull);
    expect(stored!.resourceKey, 'assessment-1');
    expect(stored.payload['requirement'], {
      'kind': 'document',
      'label': 'Passeport valide',
      'required': true,
    });
    expect(stored.payload['assessment'], {
      'state': 'missing',
      'consequence': 'blocking',
      'reason': null,
    });
  });

  test('PC adapts raw Preparation owner list without a parallel model', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      expect(
        request.url.path,
        '/api/v1/preparation/journeys/journey-1/resources/',
      );
      return MockResponse(
        jsonEncode([
          {
            'id': 'resource-1',
            'title': 'Consignes',
            'description': 'À lire avant le départ.',
            'kind': 'text',
            'visibility': 'participants',
            'version': 2,
            'occurrence_id': null,
            'text': 'Présentez-vous 20 minutes avant.',
            'external_url': null,
            'download_url': null,
          },
        ]),
        200,
      );
    });
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: client.dio,
    );
    final sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    final repository = PreparationResourcesRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await repository.refresh(journeyId: 'journey-1');

    final stored = await repository.readResources('journey-1');
    expect(stored, isNotNull);
    final items = stored!.payload['items'] as List<dynamic>;
    expect(items, hasLength(1));
    expect((items.single as Map<String, dynamic>)['title'], 'Consignes');
    expect(stored.kind, PreparationResourcesRepository.projectionKind);
  });
}
