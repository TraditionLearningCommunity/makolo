import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/detail_selector.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

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
      api: MakoloApiClient(
        baseUri: Uri.parse('https://example.test/'),
        tokenStore: MemoryTokenStore(),
      ),
    );
  });

  tearDown(() async {
    repository.api.close(force: true);
    await database.close();
  });

  test(
    'Discovery source fingerprints query and keeps server pages separate',
    () {
      const first = DiscoveryQuery(text: 'concert', page: 1, pageSize: 24);
      const second = DiscoveryQuery(text: 'concert', page: 2, pageSize: 24);

      final firstSource = repository.itemsSource(first);
      final secondSource = repository.itemsSource(second);

      expect(firstSource.owner, 'Discovery');
      expect(firstSource.projectionKind, 'discovery.items');
      expect(firstSource.path, contains('q=concert'));
      expect(firstSource.path, contains('page=1'));
      expect(secondSource.path, contains('page=2'));
      expect(firstSource.resourceKey, isNot(secondSource.resourceKey));
    },
  );

  test('Map corpus identity ignores collection page', () {
    const first = DiscoveryQuery(text: 'concert', page: 1);
    const second = DiscoveryQuery(text: 'concert', page: 4);

    final firstSource = repository.mapSource(first);
    final secondSource = repository.mapSource(second);

    expect(firstSource.path, secondSource.path);
    expect(firstSource.resourceKey, secondSource.resourceKey);
    expect(firstSource.path, isNot(contains('page=')));
  });

  test(
    'Discovery selector preserves server order and does not invent save',
    () {
      final projection = StoredProjection(
        kind: DiscoveryRepository.itemsProjectionKind,
        schemaVersion: 1,
        receivedAt: DateTime.utc(2026, 9, 30),
        payload: const {
          'count': 2,
          'page': 1,
          'page_size': 24,
          'has_next': false,
          'results': [
            {
              'identity': {
                'family': 'activity',
                'resource': {'kind': 'activity', 'id': 'activity-b'},
                'occurrence': {'kind': 'occurrence', 'id': 'occurrence-b'},
              },
              'representation': {
                'title': 'Second selon le serveur',
                'summary': '',
              },
              'saved': {'state': 'not_saved'},
              'capabilities': ['view'],
              'links': {
                'detail': '/api/v1/discovery/items/activity/activity-b/',
              },
            },
            {
              'identity': {
                'family': 'activity',
                'resource': {'kind': 'activity', 'id': 'activity-a'},
                'occurrence': {'kind': 'occurrence', 'id': 'occurrence-a'},
              },
              'representation': {
                'title': 'Premier alphabétiquement',
                'summary': '',
              },
              'saved': {'state': 'not_saved'},
              'capabilities': ['view', 'save'],
              'links': {
                'detail': '/api/v1/discovery/items/activity/activity-a/',
              },
            },
          ],
        },
      );

      final selected = const DiscoverySelector().collection(projection);

      expect(selected.items.map((item) => item.id), [
        'activity-b',
        'activity-a',
      ]);
      expect(selected.items.first.canSave, isFalse);
      expect(selected.items.last.canSave, isTrue);
    },
  );

  test('Real empty Discovery remains empty', () {
    final projection = StoredProjection(
      kind: DiscoveryRepository.itemsProjectionKind,
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 9, 30),
      payload: const {
        'count': 0,
        'page': 1,
        'page_size': 24,
        'has_next': false,
        'results': [],
      },
    );

    final selected = const DiscoverySelector().collection(projection);

    expect(selected.items, isEmpty);
    expect(selected.count, 0);
  });

  test('Map selector consumes only owner coordinates', () {
    final projection = StoredProjection(
      kind: DiscoveryRepository.mapProjectionKind,
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 9, 30),
      payload: const {
        'results': [
          {
            'activity_id': 'activity-1',
            'occurrence_id': 'occurrence-1',
            'title': 'Concert',
            'place': {
              'name': 'Salle A',
              'locality': 'Lubumbashi',
              'latitude': -11.66,
              'longitude': 27.48,
            },
          },
          {
            'activity_id': 'activity-2',
            'occurrence_id': 'occurrence-2',
            'title': 'Sans coordonnées',
            'place': {'name': 'Lieu'},
          },
        ],
      },
    );

    final points = const DiscoverySelector().mapPoints(projection);

    expect(points, hasLength(1));
    expect(points.single.activityId, 'activity-1');
    expect(points.single.latitude, -11.66);
  });

  test('Activity and Occurrence sources stay owner-backed and keyed', () {
    final activity = repository.activitySource('activity-1');
    final occurrence = repository.occurrenceSource('occurrence-1');

    expect(activity.owner, 'Activities');
    expect(activity.path, 'api/v1/activities/activity-1/');
    expect(activity.projectionKind, 'activity.detail');
    expect(activity.resourceKey, 'activity-1');

    expect(occurrence.owner, 'Occurrences');
    expect(occurrence.path, 'api/v1/occurrences/occurrence-1/');
    expect(occurrence.projectionKind, 'occurrence.detail');
    expect(occurrence.resourceKey, 'occurrence-1');
  });

  test('Occurrence selector never derives day-of without owner capability', () {
    final projection = StoredProjection(
      kind: DiscoveryRepository.occurrenceProjectionKind,
      resourceKey: 'occurrence-1',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 9, 30),
      payload: const {
        'activity': {
          'kind': 'activity',
          'id': 'activity-1',
          'title': 'Concert',
        },
        'state': {'code': 'scheduled'},
        'availability': {'state': 'available'},
        'timing': {'start_at': '2026-10-04T07:00:00+00:00'},
        'capabilities': [],
      },
    );

    final selected = const DiscoveryDetailSelector().occurrence(
      projection,
      now: DateTime.utc(2026, 10, 4, 12),
    );

    expect(selected, isNotNull);
    expect(selected!.state, 'Prévu');
    expect(selected.availability, 'Disponible');
    expect(selected.timing, isNot(contains('2026-10-04T')));
    expect(selected.canOpenDayOf, isFalse);
  });

  test('Watch replay is an owner collection source, not a local engine', () {
    final source = repository.watchResultsSource('watch-1', page: 3);

    expect(source.owner, 'Discovery');
    expect(
      source.path,
      'api/v1/discovery/watches/watch-1/results/?page=3&page_size=24',
    );
    expect(source.projectionKind, 'discovery.watch-results');
    expect(source.resourceKey, 'watch-1:3');
  });

  test('Projection snapshots remain isolated by Profile', () async {
    await store.putProjection(
      kind: DiscoveryRepository.itemsProjectionKind,
      resourceKey: 'query',
      schemaVersion: 1,
      payload: const {'results': []},
    );
    final other = ProfileStore(database, 'profile-b');

    expect(
      await other.readProjection(
        DiscoveryRepository.itemsProjectionKind,
        resourceKey: 'query',
      ),
      isNull,
    );
  });
}
