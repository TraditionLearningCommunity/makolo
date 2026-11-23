import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_possibility_unit.dart';

import 'support/presentation_harness.dart';

DiscoveryItemPresentation _candidate({
  required String family,
  required String id,
  required Map<String, dynamic> engagement,
}) => DiscoveryItemPresentation(
  family: family,
  id: id,
  candidateKey: '$family:$id',
  title: 'Possibilité autorisée',
  summary: 'Lecture N2',
  savedState: 'not_saved',
  capabilities: const {'view'},
  links: const {},
  wire: {'engagement': engagement},
);

void main() {
  test(
    'Watch criteria exclude navigation, opaque tokens and personal scope',
    () {
      const query = DiscoveryQuery(
        text: 'formation',
        place: 'Lubumbashi',
        vertical: 'event',
        latitude: -11.66,
        longitude: 27.48,
        radiusKm: 10,
        page: 3,
        pageSize: 15,
        continuation: 'signed-data',
      );
      final criteria = query.watchCriteria;
      expect(criteria['q'], 'formation');
      expect(criteria['place'], 'Lubumbashi');
      expect(criteria['lat'], '-11.66');
      expect(criteria, isNot(contains('page')));
      expect(criteria, isNot(contains('page_size')));
      expect(criteria, isNot(contains('continuation')));
      expect(criteria, isNot(contains('selected')));
      expect(criteria, isNot(contains('profile_id')));
    },
  );

  test('Save, Watch and Sharing have separate API paths and confirmations', () {
    final repository = File('lib/features/discovery/discovery_repository.dart')
        .readAsStringSync();
    final watcher = File('lib/features/discovery/discovery_watch_screens.dart')
        .readAsStringSync();
    final share = File('lib/features/discovery/discovery_share_sheet.dart')
        .readAsStringSync();
    final sharedLink = File(
      'lib/features/discovery/discovery_shared_link_screen.dart',
    ).readAsStringSync();
    expect(
      repository,
      contains(r'api/v1/discovery/items/$family/$id/saved/'),
      reason: 'Save uses a possibility owner state, not a Watch.',
    );
    expect(repository, contains('Future<String> createWatch('));
    expect(repository, contains('Future<void> updateWatchStatus('));
    expect(repository, contains('Future<void> deleteWatch('));
    expect(repository, contains('Saved state was not confirmed'));
    expect(watcher, contains('discover-watch-manage-'));
    expect(watcher, contains('widget.onOpenItem(item.family, item.id)'));
    expect(share, contains("payload['delivery_id'] is! String"));
    expect(share, contains('Sharing authority unavailable'));
    expect(share, contains('generation != _itemGeneration'));
    expect(sharedLink, contains('requireAuthentication('));
    expect(sharedLink, contains("payload['route'] != expected"));
  });

  testWidgets('a delayed Save confirmation cannot mark another item saved', (
    tester,
  ) async {
    final pending = Completer<void>();
    DiscoveryItemPresentation item(String id) => DiscoveryItemPresentation(
      family: 'activity',
      id: id,
      candidateKey: 'activity:$id',
      title: 'Possibilité $id',
      summary: '',
      savedState: 'not_saved',
      capabilities: const {'view', 'save'},
      links: const {},
      wire: const {},
    );
    final shown = ValueNotifier(item('first'));
    await PresentationHarness.pump(
      tester,
      viewport: const Size(390, 840),
      child: ValueListenableBuilder<DiscoveryItemPresentation>(
        valueListenable: shown,
        builder: (_, value, _) => DiscoveryPossibilityUnit(
          item: value,
          onOpen: () {},
          onSave: () => pending.future,
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('discover-save-n1')));
    await tester.pump();
    shown.value = item('second');
    await tester.pump();
    pending.complete();
    await tester.pump();
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('discover-save-n1')))
          .tooltip,
      'Enregistrer',
    );
    shown.dispose();
  });

  testWidgets('N3 only opens owner API-verified commerce checkout', (
    tester,
  ) async {
    final valid = _candidate(
      family: 'activity',
      id: 'activity-7',
      engagement: const {
        'owner': 'commerce',
        'state': 'owner_api',
        'capabilities': ['inspect_offers'],
        'resource': {'kind': 'activity', 'id': 'activity-7'},
        'primary_action': {
          'code': 'inspect_offers',
          'label': 'Choisir une offre',
          'destination': {
            'kind': 'native',
            'path': '/commerce/activities/activity-7/checkout',
          },
        },
      },
    );
    String? action;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(390, 840),
      child: SingleChildScrollView(
        child: DiscoveryPossibilityUnit(
          item: valid,
          detailMode: true,
          onOpen: () => fail('Owner N3 must not fall back to N2'),
          onNativeAction: (path) => action = path,
        ),
      ),
    );
    final cta = find.byKey(const Key('discover-primary-n2'));
    expect(cta, findsOneWidget);
    await tester.ensureVisible(cta);
    await tester.tap(cta);
    await tester.pump();
    expect(action, '/commerce/activities/activity-7/checkout');
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'N3 rejects an invented checkout and does not perform any action',
    (tester) async {
      final invalid = _candidate(
        family: 'activity',
        id: 'activity-7',
        engagement: const {
          'owner': 'commerce',
          'state': 'owner_api',
          'capabilities': ['inspect_offers'],
          'resource': {'kind': 'activity', 'id': 'activity-7'},
          'primary_action': {
            'code': 'inspect_offers',
            'destination': {
              'kind': 'native',
              'path': '/commerce/activities/someone-else/checkout',
            },
          },
        },
      );
      var opened = false;
      await PresentationHarness.pump(
        tester,
        viewport: const Size(390, 840),
        child: DiscoveryPossibilityUnit(
          item: invalid,
          detailMode: true,
          onOpen: () => opened = true,
          onNativeAction: (_) => opened = true,
        ),
      );
      expect(find.byKey(const Key('discover-primary-n2')), findsNothing);
      expect(opened, isFalse);
    },
  );

  testWidgets(
    'N3 preserves native Event ticket choice without a fake purchase',
    (tester) async {
      final event = _candidate(
        family: 'activity',
        id: 'event-activity',
        engagement: const {
          'owner': 'events',
          'state': 'owner_api',
          'capabilities': ['inspect_offers'],
          'resource': {
            'kind': 'event',
            'id': 'event-7',
            'slug': 'gospel-night',
          },
          'links': {'native': '/events/gospel-night/tickets'},
          'primary_action': {
            'code': 'inspect_offers',
            'label': 'Voir les billets',
            'destination': {
              'kind': 'native',
              'path': '/events/gospel-night/tickets',
            },
          },
        },
      );
      String? path;
      await PresentationHarness.pump(
        tester,
        viewport: const Size(390, 840),
        child: DiscoveryPossibilityUnit(
          item: event,
          detailMode: true,
          onOpen: () => fail('No artificial purchase'),
          onNativeAction: (value) => path = value,
        ),
      );
      final action = find.byKey(const Key('discover-primary-n2'));
      expect(action, findsOneWidget);
      await tester.tap(action);
      await tester.pump();
      expect(path, '/events/gospel-night/tickets');
    },
  );

  testWidgets('N3 Obtention opens only the owner choose route', (tester) async {
    final item = _candidate(
      family: 'activity',
      id: 'activity-7',
      engagement: const {
        'owner': 'obtention',
        'state': 'owner_api',
        'capabilities': ['start_journey'],
        'resource': {'kind': 'obtention', 'id': 'obtention-7'},
        'primary_action': {
          'code': 'start_journey',
          'label': 'Obtenir',
          'destination': {
            'kind': 'native',
            'path': '/obtention/obtention-7/choose',
          },
        },
      },
    );
    String? path;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(390, 840),
      child: DiscoveryPossibilityUnit(
        item: item,
        detailMode: true,
        onOpen: () => fail('No generic onboarding flow'),
        onNativeAction: (value) => path = value,
      ),
    );
    final action = find.byKey(const Key('discover-primary-n2'));
    expect(action, findsOneWidget);
    await tester.tap(action);
    await tester.pump();
    expect(path, '/obtention/obtention-7/choose');
  });

  testWidgets('N3 funding uses the exact owner contribution route', (
    tester,
  ) async {
    final funding = _candidate(
      family: 'funding_activity',
      id: 'activity-funding',
      engagement: const {
        'owner': 'funding',
        'state': 'owner_api',
        'capabilities': ['contribute'],
        'resource': {'kind': 'funding', 'id': 'funding-77'},
        'primary_action': {
          'code': 'contribute',
          'label': 'Contribuer',
          'destination': {
            'kind': 'native',
            'path': '/funding/funding-77/contribute',
          },
        },
      },
    );
    String? path;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(390, 840),
      child: DiscoveryPossibilityUnit(
        item: funding,
        detailMode: true,
        onOpen: () => fail('No fallback N2'),
        onNativeAction: (p) => path = p,
      ),
    );
    final action = find.byKey(const Key('discover-primary-n2'));
    expect(action, findsOneWidget);
    await tester.ensureVisible(action);
    await tester.tap(action);
    await tester.pump();
    expect(path, '/funding/funding-77/contribute');
  });
}
