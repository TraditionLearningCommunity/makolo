import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  late MakoloDatabase database;
  late MakoloApiClient api;
  late DiscoveryRepository repository;
  final sent = <String, Object?>{};

  setUp(() {
    sent.clear();
    database = MakoloDatabase.memory();
    final client = MockClient((request) async {
      sent[request.url.path] = jsonDecode(request.body);
      if (request.url.path.endsWith('/clarify/')) {
        return const MockResponse(
          '{"meta":{"projection":"discovery.clarification"},'
          '"data":{"status":"applied","query":{"q":"calme",'
          '"vertical":"event","when":"tomorrow"},"constraints":[]}}',
          200,
        );
      }
      return const MockResponse(
        '{"meta":{"projection":"discovery.source-leads"},'
        '"data":{"status":"completed","candidates":[{'
        '"label":"Piste","summary":"A vérifier",'
        '"sources":[{"url":"https://example.org/public","title":"Source"},'
        '{"url":"http://127.0.0.1/private","title":"Prive"}]}]}}',
        200,
      );
    });
    final tokenStore = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'c5-token',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    api = MakoloApiClient(
      baseUri: Uri.parse('https://example.invalid/'),
      dio: client.dio,
      tokenStore: tokenStore,
    );
    repository = DiscoveryRepository(
      database: database,
      store: ProfileStore(database, 'profile-a'),
      profileId: 'profile-a',
      api: api,
    );
  });

  tearDown(() async {
    api.close(force: true);
    await database.close();
  });

  test('clarification calls owner explicitly with bounded criteria', () async {
    final result = await repository.clarifySearch(
      const DiscoveryQuery(
        text: 'une sortie calme demain',
        page: 3,
        continuation: 'opaque',
      ),
    );
    expect(result.status, 'applied');
    expect(result.criteria['vertical'], 'event');
    final request = sent['/api/v1/discovery/clarify/'] as Map<String, dynamic>;
    final criteria = request['criteria'] as Map<String, dynamic>;
    expect(criteria['q'], 'une sortie calme demain');
    expect(criteria.containsKey('continuation'), isFalse);
    expect(criteria.containsKey('profile_id'), isFalse);
    expect(criteria.containsKey('page'), isFalse);
  });

  test(
    'external leads are transient and only expose safe https links',
    () async {
      final response = await repository.researchSources('bourses');
      expect(response.status, 'completed');
      expect(response.leads, hasLength(1));
      expect(response.leads.single.url.host, 'example.org');
      expect(sent['/api/v1/discovery/research/'], {'q': 'bourses'});
    },
  );
}
