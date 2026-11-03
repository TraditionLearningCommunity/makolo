import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/features/discovery/discovery_wire.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

Map<String, dynamic> candidate(String family, String id) => {
  'identity': {
    'family': family,
    'candidate_key': '$family:$id',
    'resource': {'kind': family, 'id': id},
    'occurrence': null,
    'revision': {'kind': 'revision', 'id': 'rev-$id'},
  },
  'representation': {'kind': family, 'title': 'Possibilité $id'},
  'owner': {'display_name': 'Espace public'},
  'place': null,
  'timing': null,
  'price': {'state': 'unknown'},
  'availability': {'state': 'unknown'},
  'saved': {'state': 'unknown'},
  'watch': {'state': 'unknown'},
  'personal_relation': {'state': 'unknown'},
  'provenance': {
    'resources': [
      {'kind': family, 'id': id},
    ],
  },
  'assessment': [
    {
      'state': 'unknown',
      'code': 'availability_not_resolved',
      'provenance': 'availability',
    },
  ],
  'variants': <Object>[],
  'relations': <Object>[],
  'temporal_facts': <Object>[],
  'spatial_facts': <Object>[],
  'media_bindings': <Object>[],
  'capabilities': <String>[],
  'links': {'detail': '/api/v1/discovery/items/$family/$id/'},
};

Map<String, dynamic> envelope({
  String scope = 'public',
  String projection = 'discovery.items',
  int version = 1,
  List<Map<String, dynamic>>? candidates,
  bool hasNext = false,
}) {
  final results =
      candidates ??
      [
        candidate('activity', 'a'),
        candidate('service_activity', 's'),
        candidate('funding_activity', 'f'),
        candidate('opportunity', 'o'),
      ];
  return {
    'meta': {
      'projection': projection,
      'schema_version': version,
      'scope': scope,
      'generated_at': '2026-10-17T12:00:00+00:00',
    },
    'data': {
      'surface': scope == 'public' ? 'discover_public' : 'discover_me',
      'actor': scope == 'public' ? null : {'type': 'profile', 'id': 'p-1'},
      'viewer': scope == 'public' ? null : {'type': 'profile', 'id': 'p-1'},
      'count': results.length + (hasNext ? 1 : 0),
      'page': 1,
      'page_size': 20,
      'has_next': hasNext,
      'has_previous': false,
      'results': results,
      'items': results,
      'selection': {
        'state': results.isEmpty ? 'empty' : 'ready',
        'reason': null,
      },
      'terminal': {'state': results.isEmpty ? 'empty' : 'ok', 'message': null},
      'continuation': {
        'state': hasNext ? 'more' : 'end',
        'token': hasNext ? 'opaque.signed.cursor' : null,
      },
      'freshness': {'state': 'fresh', 'fact_freshness': 'not_asserted'},
      'exploration': {'raw_text': '', 'constraints': []},
    },
  };
}

void main() {
  const selector = DiscoverySelector();

  test(
    'N3 owner denial invalidates previews but network outage preserves them',
    () {
      expect(
        const DiscoverySourceState(
          invalidated: true,
          lastErrorCode: 'permission_denied',
        ).ownerUnavailable,
        isTrue,
      );
      expect(
        const DiscoverySourceState(
          invalidated: true,
          lastErrorCode: 'not_found',
        ).ownerUnavailable,
        isTrue,
      );
      expect(
        const DiscoverySourceState(
          invalidated: true,
          lastErrorCode: 'api_error',
        ).ownerUnavailable,
        isTrue,
      );
      expect(
        const DiscoverySourceState(
          invalidated: true,
          lastErrorCode: 'timeout',
        ).ownerUnavailable,
        isFalse,
      );
      expect(
        const DiscoverySourceState(
          invalidated: false,
          lastErrorCode: 'permission_denied',
        ).ownerUnavailable,
        isFalse,
      );
    },
  );

  test('B1 four families preserve identity and unknown owner facts', () {
    final wire = DiscoveryWire.receive(envelope(), scope: 'public');
    final collection = selector.publicCollection(wire.snapshotPayload);
    expect(collection.items.map((item) => item.family), [
      'activity',
      'service_activity',
      'funding_activity',
      'opportunity',
    ]);
    expect(collection.items.first.revisionId, 'rev-a');
    expect(collection.items.first.assessment.single['state'], 'unknown');
    expect(collection.items.first.priceFacts?['state'], 'unknown');
    expect(collection.items.first.saved?['state'], 'unknown');
    expect(collection.items.first.watch?['state'], 'unknown');
    expect(collection.envelopeMeta?['scope'], 'public');
    expect(collection.freshness?['fact_freshness'], 'not_asserted');
    expect(collection.items.first.capabilities, isEmpty);
  });

  test('beta-shaped public Services wire accepts 12 items, aliases and opaque continuation', () {
    final services = List.generate(12, (index) {
      final item = candidate('service_activity', 'synthetic-$index');
      item['representation'] = {
        'kind': 'service',
        'presentation_kind': 'service',
        'vertical_label': 'Accompagnement',
        'title': 'Accompagnement synthétique $index',
        'summary': 'Jeu de test, sans relation personnelle.',
        'image_url': null,
        'route_label': null,
        'eyebrow': 'Orientation',
      };
      item['capabilities'] = <String>['view'];
      item['personal_relation'] = {
        'state': 'none',
        'availability': 'available',
        'expires_at': null,
      };
      item['engagement'] = {
        'state': 'owner_contract',
        'owner': 'services',
        'capabilities': <String>[],
        'links': <String, dynamic>{},
        'presentation': {
          'label': 'Commencer',
          'capability': 'start',
          'enabled': false,
          'web': '/services/synthetic-$index/start/',
          'web_enabled': true,
        },
      };
      item['detail'] = {'description': 'Donnée synthétique de test.'};
      item['media_bindings'] = <Map<String, dynamic>>[];
      return item;
    });
    final response = envelope(candidates: services, hasNext: true);
    final data = response['data'] as Map<String, dynamic>;
    data['page_size'] = 12;
    data['count'] = 191;
    data['items'] = services;
    final wire = DiscoveryWire.receive(response, scope: 'public');
    final collection = selector.publicCollection(wire.snapshotPayload);

    expect(collection.count, 191);
    expect(collection.items, hasLength(12));
    expect(
      collection.items.every((item) => item.family == 'service_activity'),
      isTrue,
    );
    expect(collection.hasNext, isTrue);
    expect(collection.continuationToken, 'opaque.signed.cursor');
    expect(
      collection.items.every((item) => !item.capabilities.contains('start')),
      isTrue,
    );
    expect(
      collection.items.first.engagement?['presentation'],
      containsPair('enabled', false),
    );
    expect(collection.items.first.representationKind, 'service');
  });

  test('B1 public and personal use identical semantic interpretation', () {
    final guest = DiscoveryWire.receive(envelope(), scope: 'public');
    final me = DiscoveryWire.receive(
      envelope(scope: 'personal'),
      scope: 'personal',
    );
    final guestItem = selector
        .publicCollection(guest.snapshotPayload)
        .items
        .first;
    final meItem = selector
        .collection(
          StoredProjection(
            kind: DiscoveryRepository.itemsProjectionKind,
            schemaVersion: 1,
            receivedAt: DateTime.utc(2026, 10, 17),
            payload: me.snapshotPayload,
          ),
        )
        .items
        .first;
    expect(meItem.candidateKey, guestItem.candidateKey);
    expect(meItem.assessment, guestItem.assessment);
    expect(meItem.provenance, guestItem.provenance);
  });

  test('B1 unexpected projection, version and scope are contract errors', () {
    expect(
      () => DiscoveryWire.receive(
        envelope(projection: 'unrelated.items'),
        scope: 'public',
      ),
      throwsFormatException,
    );
    expect(
      () => DiscoveryWire.receive(envelope(version: 2), scope: 'public'),
      throwsFormatException,
    );
    expect(
      () => DiscoveryWire.receive(envelope(scope: 'personal'), scope: 'public'),
      throwsFormatException,
    );
  });

  test('B1 guest rejects private actor and viewer leakage', () {
    final body = envelope();
    (body['data'] as Map<String, dynamic>)['viewer'] = {
      'type': 'profile',
      'id': 'p-1',
    };
    expect(
      () => DiscoveryWire.receive(body, scope: 'public'),
      throwsFormatException,
    );
  });

  test('B1 rejects invalid essential identity or malformed facts', () {
    final body = envelope();
    final data = body['data'] as Map<String, dynamic>;
    final rows = data['results'] as List<Map<String, dynamic>>;
    (rows.first['identity'] as Map<String, dynamic>)['candidate_key'] = '';
    expect(
      () => DiscoveryWire.receive(body, scope: 'public'),
      throwsFormatException,
    );
    final other = envelope();
    final otherRows =
        (other['data'] as Map<String, dynamic>)['results']
            as List<Map<String, dynamic>>;
    otherRows.first['relations'] = {'kind': 'not-a-list'};
    expect(
      () => DiscoveryWire.receive(other, scope: 'public'),
      throwsFormatException,
    );
  });

  test('B1 retains n-ary relations, variants, multiple facts and media', () {
    final body = envelope();
    final data = body['data'] as Map<String, dynamic>;
    final rows = data['results'] as List<Map<String, dynamic>>;
    rows.first['relations'] = [
      {
        'kind': 'complement',
        'members': ['activity:a', 'service_activity:s', 'opportunity:o'],
      },
    ];
    rows.first['variants'] = [
      {'id': 'version-1', 'kind': 'alternative'},
    ];
    rows.first['temporal_facts'] = [
      {'role': 'start', 'date': '2026-10-17'},
      {'role': 'end', 'date': '2026-10-19'},
    ];
    rows.first['spatial_facts'] = [
      {
        'role': 'departure',
        'place': {'latitude': -11.66, 'longitude': 27.48},
      },
      {
        'role': 'arrival',
        'place': {'latitude': -10.72, 'longitude': 25.47},
      },
    ];
    rows.first['media_bindings'] = [
      {
        'resource': {'kind': 'image', 'id': 'media-1'},
        'target': 'card',
        'purpose': 'illustration',
      },
    ];
    final wire = DiscoveryWire.receive(body, scope: 'public');
    final collection = selector.publicCollection(wire.snapshotPayload);
    final item = collection.items.first;
    expect(item.relations.single['members'], hasLength(3));
    expect(item.variants, hasLength(1));
    expect(item.temporalFacts, hasLength(2));
    expect(item.mediaBindings, hasLength(1));
    expect(selector.spatialAnchorsFromCollection(collection), hasLength(2));
    expect(
      selector.spatialAnchorsFromCollection(collection).first.candidateKey,
      item.candidateKey,
    );
  });

  test('opaque continuation never needs client-side decoding', () {
    final wire = DiscoveryWire.receive(
      envelope(hasNext: true),
      scope: 'public',
    );
    final collection = selector.publicCollection(wire.snapshotPayload);
    expect(collection.continuationToken, 'opaque.signed.cursor');
    const query = DiscoveryQuery(text: 'formation', pageSize: 20);
    final next = query.copyWith(
      page: 2,
      continuation: collection.continuationToken,
    );
    expect(next.parameters['continuation'], collection.continuationToken);
    expect(next.path, contains('continuation='));
    expect(next.mapCanonicalQuery, isNot(contains('continuation=')));
    expect(query.parameters.containsKey('continuation'), isFalse);
  });

  test('next lot reconciles identity and preserves stable server order', () {
    final first = selector.publicCollection({
      'results': [candidate('activity', 'a'), candidate('opportunity', 'o')],
      'count': 3,
      'page': 1,
      'page_size': 2,
      'has_next': true,
    });
    final updated = candidate('opportunity', 'o');
    (updated['representation'] as Map<String, dynamic>)['title'] = 'Updated';
    final second = selector.publicCollection({
      'results': [updated, candidate('activity', 'b')],
      'count': 3,
      'page': 2,
      'page_size': 2,
      'has_next': false,
    });
    final merged = first.reconcile(second);
    expect(merged.items.map((item) => item.candidateKey), [
      'activity:a',
      'opportunity:o',
      'activity:b',
    ]);
    expect(merged.items[1].title, 'Updated');
    expect(merged.page, 2);
    expect(merged.hasNext, isFalse);
    expect(() => second.reconcile(first), returnsNormally);
  });

  test(
    'offline one-shot and watched Discovery reads reconcile the same pages',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'p-1');
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(),
      );
      addTearDown(api.close);
      final repository = DiscoveryRepository(
        database: database,
        store: store,
        profileId: 'p-1',
        api: api,
      );
      const firstQuery = DiscoveryQuery(pageSize: 20);
      final first = envelope(
        scope: 'personal',
        candidates: [candidate('activity', 'a')],
        hasNext: true,
      );
      final firstWire = DiscoveryWire.receive(first, scope: 'personal');
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: firstQuery.fingerprint,
        schemaVersion: 1,
        payload: firstWire.snapshotPayload,
      );
      final secondQuery = firstQuery.copyWith(
        page: 2,
        continuation: 'opaque.signed.cursor',
      );
      expect(await repository.readItems(secondQuery), isNull);
      expect(await repository.watchItems(secondQuery).first, isNull);
      final second = envelope(
        scope: 'personal',
        candidates: [candidate('opportunity', 'b')],
      );
      final secondData = second['data'] as Map<String, dynamic>;
      secondData['page'] = 2;
      secondData['count'] = 2;
      secondData['has_previous'] = true;
      final secondWire = DiscoveryWire.receive(second, scope: 'personal');
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: secondQuery.fingerprint,
        schemaVersion: 1,
        payload: secondWire.snapshotPayload,
      );

      final offline = await repository.readItems(secondQuery);
      final watched = await repository.watchItems(secondQuery).first;
      expect(offline, isNotNull);
      expect(watched, isNotNull);
      final offlineItems = selector.collection(offline!).items;
      final watchedItems = selector.collection(watched!).items;
      expect(offlineItems.map((item) => item.candidateKey), [
        'activity:a',
        'opportunity:b',
      ]);
      expect(
        watchedItems.map((item) => item.candidateKey),
        offlineItems.map((item) => item.candidateKey),
      );
      expect(
        (await store.readProjection(
          DiscoveryRepository.itemsProjectionKind,
          resourceKey: secondQuery.fingerprint,
        ))!.payload['results'],
        hasLength(1),
      );
    },
  );

  test('old snapshot is readable; malformed snapshot is not NO_MATCH', () {
    final legacy = selector.publicCollection({
      'results': [candidate('activity', 'a')],
      'count': 1,
      'page': 1,
      'page_size': 24,
      'has_next': false,
    });
    expect(legacy.items, hasLength(1));

    final invalid = selector.select(
      projection: StoredProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        schemaVersion: 1,
        receivedAt: DateTime.utc(2026, 10, 17),
        payload: {
          'results': [<String, dynamic>{}],
        },
      ),
      hasCriteria: true,
    );
    expect(invalid.states, contains(DiscoveryFieldState.contractError));
    expect(invalid.states, isNot(contains(DiscoveryFieldState.noMatch)));
  });
}
