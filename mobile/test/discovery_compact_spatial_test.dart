import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _OfflineApi implements MakoloApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> _candidate(String id, {bool detailed = false}) => {
  'identity': {
    'family': 'activity',
    'candidate_key': 'activity:$id',
    'resource': {'kind': 'activity', 'id': id},
    'occurrence': {'kind': 'occurrence', 'id': 'occ-$id'},
  },
  'representation': {
    'title': 'Possibility $id',
    'kind': 'event',
    'eyebrow': 'Événement',
  },
  'owner': {'display_name': 'Espace public'},
  'timing': {'start_at': '2026-11-09T14:00:00+00:00'},
  'place': {'name': 'Place $id', 'latitude': -11.66, 'longitude': 27.48},
  'spatial_facts': [
    {
      'role': 'departure',
      'place': {'name': 'Origin', 'latitude': -11.66, 'longitude': 27.48},
    },
    {
      'role': 'arrival',
      'place': {'name': 'Destination', 'latitude': -10.71, 'longitude': 25.47},
    },
  ],
  'capabilities': ['view'],
  'links': {'detail': '/api/v1/discovery/items/activity/$id/'},
  if (detailed) 'detail': {'description': 'Authorized detail for $id'},
  if (detailed) 'resources': <Map<String, dynamic>>[],
};

Map<String, dynamic> _field({String spatialViewer = 'profile-a'}) => {
  'viewer': {'type': 'profile', 'id': 'profile-a'},
  'count': 2,
  'page': 1,
  'page_size': 24,
  'has_next': false,
  'results': [_candidate('first', detailed: true)],
  'spatial_index': {
    'count': 2,
    'total_results': 2,
    'detail_available': false,
    'viewer': {'type': 'profile', 'id': spatialViewer},
    'results': [_candidate('first'), _candidate('second')],
  },
};

void main() {
  late MakoloDatabase database;
  late ProfileStore store;
  late DiscoveryRepository repository;

  setUp(() {
    database = MakoloDatabase.memory();
    store = ProfileStore(database, 'profile-a');
    repository = DiscoveryRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      api: _OfflineApi(),
    );
  });

  tearDown(() async {
    await database.close();
  });

  test('N1 requests the compact map index in its single owner acquisition', () {
    final path = repository.itemsSource(const DiscoveryQuery()).path;
    expect(path, contains('include_spatial_index=compact'));
    expect(path, isNot(contains('include_spatial_index=1')));
  });

  test(
    'compact spatial map keeps all locations without a second map cache',
    () async {
      const query = DiscoveryQuery();
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: query.fingerprint,
        schemaVersion: 1,
        payload: _field(),
      );

      final spatial = await repository.readSpatial(query);
      expect(spatial?.payload['detail_available'], false);
      final selection = const DiscoverySelector().spatialSelection(
        projection: spatial,
      );
      expect(selection.collection.items, hasLength(2));
      final compactItem = selection.collection.items.last;
      expect(compactItem.representationKind, 'event');
      expect(compactItem.eyebrow, 'Événement');
      expect(compactItem.owner, 'Espace public');
      expect(compactItem.timing, isNotNull);
      expect(compactItem.canSave, isFalse);
      expect(compactItem.links['detail'], isNotNull);
      final anchors = const DiscoverySelector().spatialAnchorsFromCollection(
        selection.collection,
      );
      expect(
        anchors.where((anchor) => anchor.candidateKey == 'activity:second'),
        hasLength(2),
      );
      expect(
        anchors.map((anchor) => anchor.fact['role']).toSet(),
        containsAll(['departure', 'arrival']),
      );

      // Detailed first-page facts remain locally reusable for N2.
      final known = await repository.readItem('activity', 'first');
      expect((known?.payload['item'] as Map?)?['detail'], {
        'description': 'Authorized detail for first',
      });
      // A compact-only pin never pretends to hold a full N2: fetch on demand.
      expect(await repository.readItem('activity', 'second'), isNull);
      expect(
        await store.readProjection(
          DiscoveryRepository.mapProjectionKind,
          resourceKey: query.mapFingerprint,
        ),
        isNull,
      );
    },
  );

  test(
    'Service appears on the unpaginated map although absent from N1 page',
    () async {
      const query = DiscoveryQuery(pageSize: 1);
      final field = _field();
      field['page_size'] = 1;
      final index = Map<String, dynamic>.from(field['spatial_index'] as Map);
      final service = _candidate('service');
      service['identity'] = {
        'family': 'service_activity',
        'candidate_key': 'service_activity:service',
        'resource': {'kind': 'activity', 'id': 'service'},
        'occurrence': null,
      };
      service['representation'] = {
        'kind': 'service',
        'title': 'Service demo Maseru',
        'eyebrow': 'Service',
      };
      service['place'] = {
        'name': 'Maseru',
        'latitude': -29.315,
        'longitude': 27.483,
      };
      service['spatial_facts'] = [
        {
          'role': 'primary',
          'place': {'name': 'Maseru', 'latitude': -29.315, 'longitude': 27.483},
        },
      ];
      index['results'] = [_candidate('first'), service];
      field['spatial_index'] = index;
      await store.putProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        resourceKey: query.fingerprint,
        schemaVersion: 1,
        payload: field,
      );

      final n1 = await repository.readItems(query);
      final list = const DiscoverySelector().collection(n1);
      expect(list.items, hasLength(1));
      expect(list.items.first.family, 'activity');
      final map = await repository.readSpatial(query);
      final selection = const DiscoverySelector().spatialSelection(
        projection: map,
      );
      expect(selection.collection.items, hasLength(2));
      final serviceItem = selection.collection.items.last;
      expect(serviceItem.family, 'service_activity');
      expect(serviceItem.isMappable, isTrue);
      expect(serviceItem.occurrenceId, isNull);
      expect(serviceItem.latitude, -29.315);
      expect(serviceItem.longitude, 27.483);
      final anchors = const DiscoverySelector().spatialAnchorsFromCollection(
        selection.collection,
      );
      expect(
        anchors.where(
          (anchor) => anchor.candidateKey == 'service_activity:service',
        ),
        hasLength(1),
      );
      expect(await repository.readItem('service_activity', 'service'), isNull);
    },
  );

  test('spatial projection cannot cross the viewer boundary', () async {
    const query = DiscoveryQuery();
    await store.putProjection(
      kind: DiscoveryRepository.itemsProjectionKind,
      resourceKey: query.fingerprint,
      schemaVersion: 1,
      payload: _field(spatialViewer: 'profile-b'),
    );
    expect(await repository.readSpatial(query), isNull);
  });
}
