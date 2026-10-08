import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/sync/freshness.dart';

StoredProjection fieldProjection({
  List<Map<String, Object?>> results = const [],
  bool hasNext = false,
}) {
  return StoredProjection(
    kind: DiscoveryRepository.itemsProjectionKind,
    schemaVersion: 1,
    receivedAt: DateTime.utc(2026, 10, 3, 12),
    payload: {
      'count': results.length,
      'page': 1,
      'page_size': 24,
      'has_next': hasNext,
      'results': results,
    },
  );
}

Map<String, Object?> possibility(
  String id,
  String title, {
  double? latitude,
  double? longitude,
  String? imageUrl,
  String family = 'activity',
  String? occurrenceId,
  List<String> capabilities = const ['view'],
}) {
  return {
    'identity': {
      'family': family,
      'candidate_key': '$family:$id',
      'resource': {'kind': 'activity', 'id': id},
      'occurrence': occurrenceId == null
          ? null
          : {'kind': 'occurrence', 'id': occurrenceId},
    },
    'representation': {
      'kind': family == 'activity' ? 'event' : family,
      'title': title,
      'summary': 'Résumé $title',
      'image_url': imageUrl,
      'eyebrow': 'À explorer',
    },
    'place': latitude == null || longitude == null
        ? null
        : {
            'name': 'Lieu $id',
            'locality': 'Lubumbashi',
            'latitude': latitude,
            'longitude': longitude,
            'distance_km': id == 'far' ? 250.0 : 2.0,
          },
    'timing': null,
    'owner': {'display_name': 'Espace test'},
    'availability': {'state': 'available'},
    'price': {'state': 'unknown'},
    'saved': {'state': 'not_saved'},
    'capabilities': capabilities,
    'links': {'detail': '/api/v1/discovery/items/$family/$id/'},
  };
}

void main() {
  const selector = DiscoverySelector();

  test('parses real discovery.items shape and preserves server order', () {
    final projection = fieldProjection(
      results: [
        possibility('second', 'Second selon le serveur'),
        possibility('first', 'Premier alphabétiquement'),
      ],
    );

    final selected = selector.collection(projection);

    expect(selected.items.map((item) => item.id), ['second', 'first']);
  });

  test('NO_MATCH is criteria-bound and never widens silently', () {
    final selected = selector.select(
      projection: fieldProjection(),
      hasCriteria: true,
    );

    expect(selected.collection.items, isEmpty);
    expect(selected.states, contains(DiscoveryFieldState.noMatch));
    expect(
      selected.states,
      isNot(contains(DiscoveryFieldState.noCurrentProposal)),
    );
  });

  test('NO_CURRENT_PROPOSAL is distinct from a filtered miss', () {
    final selected = selector.select(
      projection: fieldProjection(),
      hasCriteria: false,
    );

    expect(selected.states, contains(DiscoveryFieldState.noCurrentProposal));
    expect(selected.states, isNot(contains(DiscoveryFieldState.noMatch)));
  });

  test('END_OF_FIELD is explicit for a known final useful page', () {
    final selected = selector.select(
      projection: fieldProjection(
        results: [possibility('one', 'Une possibilité')],
      ),
      hasCriteria: false,
    );

    expect(selected.states, contains(DiscoveryFieldState.endOfField));
  });

  test('offline with snapshot preserves field and remains honest', () {
    final selected = selector.select(
      projection: fieldProjection(
        results: [possibility('one', 'Une possibilité')],
      ),
      hasCriteria: false,
      freshness: FreshnessState.usableButOld,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
      failure: MakoloFailureCue.recoverable,
    );

    expect(selected.collection.items, hasLength(1));
    expect(
      selected.surface.reachability,
      MakoloReachabilityCue.temporarilyUnavailable,
    );
    expect(selected.surface.failure, MakoloFailureCue.recoverable);
    expect(selected.states, contains(DiscoveryFieldState.offlineWithSnapshot));
  });

  test('offline without snapshot is not presented as no result', () {
    final selected = selector.select(
      projection: null,
      hasCriteria: true,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
    );

    expect(selected.states, contains(DiscoveryFieldState.offlineNoSnapshot));
    expect(selected.states, isNot(contains(DiscoveryFieldState.noMatch)));
  });

  test('server unavailable without snapshot stays distinct from offline', () {
    final selected = selector.select(
      projection: null,
      hasCriteria: false,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
      serverUnavailable: true,
    );

    expect(
      selected.states,
      contains(DiscoveryFieldState.serverUnavailableNoSnapshot),
    );
    expect(
      selected.states,
      isNot(contains(DiscoveryFieldState.offlineNoSnapshot)),
    );
  });

  test('spatial points derive from the same collection field', () {
    final collection = selector.collection(
      fieldProjection(
        results: [
          possibility(
            'near',
            'Cartographiable',
            latitude: -11.66,
            longitude: 27.48,
            occurrenceId: 'occ-near',
          ),
          possibility('remote', 'À distance'),
        ],
      ),
    );

    final points = selector.mapPointsFromCollection(collection);

    expect(collection.items, hasLength(2));
    expect(points, hasLength(1));
    expect(points.single.candidateKey, 'activity:near');
    expect(points.single.occurrenceId, 'occ-near');
    expect(collection.items.last.isMappable, isFalse);
  });

  test(
    'media and save capabilities are represented without engagement inference',
    () {
      final collection = selector.collection(
        fieldProjection(
          results: [
            possibility(
              'media',
              'Avec média',
              imageUrl: 'https://example.test/media.jpg',
              capabilities: const ['view', 'save'],
            ),
          ],
        ),
      );

      final item = collection.items.single;
      expect(item.imageUrl, 'https://example.test/media.jpg');
      expect(item.canSave, isTrue);
      expect(item.canUnsave, isFalse);
      expect(item.capabilities, isNot(contains('engage')));
    },
  );

  test('DiscoveryQuery preserves all criteria while paging', () {
    const query = DiscoveryQuery(
      text: 'formation',
      place: 'Lubumbashi',
      when: 'tomorrow',
      period: 'morning',
      vertical: 'event',
      price: 'free',
      dateFrom: '2026-10-04',
      dateTo: '2026-10-06',
      latitude: -11.66,
      longitude: 27.48,
      radiusKm: 25,
      page: 1,
    );

    final paged = query.copyWith(page: 2);

    expect(paged.page, 2);
    expect(paged.text, 'formation');
    expect(paged.place, 'Lubumbashi');
    expect(paged.when, 'tomorrow');
    expect(paged.period, 'morning');
    expect(paged.vertical, 'event');
    expect(paged.price, 'free');
    expect(paged.dateFrom, '2026-10-04');
    expect(paged.dateTo, '2026-10-06');
    expect(paged.latitude, -11.66);
    expect(paged.parameters['page'], '2');
  });
}
