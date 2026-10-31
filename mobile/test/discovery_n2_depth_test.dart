import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_n2_model.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_n2_depth.dart';

import 'support/presentation_harness.dart';

DiscoveryItemPresentation possibility({
  String family = 'activity',
  Map<String, dynamic> wire = const {},
}) => DiscoveryItemPresentation(
  family: family,
  id: 'parent',
  candidateKey: '$family:parent',
  title: 'Formation en deux sessions',
  summary: 'Proposition publique.',
  savedState: 'not_saved',
  capabilities: const {'view'},
  links: const {},
  wire: wire,
);

void main() {
  test('N2 keeps favourable, limiting and unknown owner assessments distinct', () {
    final depth = DiscoveryN2Depth(possibility(wire: const {
      'assessment': [
        {'state': 'favorable', 'label': 'Disponible'},
        {'state': 'limiting', 'label': 'Date limite proche'},
        {'state': 'unknown', 'label': 'Éligibilité non établie'},
        {'state': 'unknown', 'label': 'Éligibilité non établie'},
        {'state': 'invented', 'label': 'Client guessed this'},
      ],
    }));
    expect(depth.assessments.map((x) => x.state),
        ['favorable', 'limiting', 'unknown']);
    expect(depth.assessments.last.label, 'Éligibilité non établie');
    expect(depth.assessments.any((x) => x.label == 'Client guessed this'), isFalse);
  });

  test('N2 compares only known shared dimensions of same owner Occurrences', () {
    final depth = DiscoveryN2Depth(possibility(wire: const {
      'identity': {'family': 'activity', 'resource': {'kind': 'activity', 'id': 'parent'}},
      'price': {'state': 'fixed', 'amount': 90, 'currency': 'USD'},
      'variants': [
        {'occurrence': {'kind': 'occurrence', 'id': 'morning'},
         'timing': {'start_date': '2026-11-12', 'start_time': '09:00', 'timezone': 'Africa/Lubumbashi'}},
        {'occurrence': {'kind': 'occurrence', 'id': 'evening'},
         'timing': {'start_date': '2026-11-12', 'start_time': '17:00', 'timezone': 'Africa/Lubumbashi'}},
        {'occurrence': {'kind': 'occurrence', 'id': 'morning'},
         'timing': {'start_date': '2026-11-13'}},
      ],
      'spatial_facts': [
        {'occurrence': {'kind': 'occurrence', 'id': 'morning'},
         'place': {'name': 'Campus A', 'locality': 'Lubumbashi'}},
        {'occurrence': {'kind': 'occurrence', 'id': 'evening'},
         'place': {'name': 'Campus B', 'locality': 'Lubumbashi'}},
      ],
    }));
    expect(depth.variants, hasLength(2));
    expect(depth.variants.first.places, ['Campus A, Lubumbashi']);
    expect(depth.variants.last.places, ['Campus B, Lubumbashi']);
    expect(depth.comparisonRows.map((x) => x.label), ['Début', 'Lieu']);
    expect(depth.comparisonRows.first.values, [
      '2026-11-12 · 09:00 · Africa/Lubumbashi',
      '2026-11-12 · 17:00 · Africa/Lubumbashi',
    ]);
    expect(depth.comparisonRows.any((x) => x.label == 'Prix'), isFalse);
    expect(depth.comparisonRows.any((x) => x.label == 'Fin'), isFalse);
  });

  test('one variant, incomplete dimension and foreign family cannot compare', () {
    final single = DiscoveryN2Depth(possibility(wire: const {
      'variants': [
        {'occurrence': {'kind': 'occurrence', 'id': 'one'},
         'timing': {'start_date': '2026-11-12'}},
      ],
    }));
    expect(single.comparisonRows, isEmpty);
    final partial = DiscoveryN2Depth(possibility(wire: const {
      'variants': [
        {'occurrence': {'kind': 'occurrence', 'id': 'one'},
         'timing': {'start_date': '2026-11-12'}},
        {'occurrence': {'kind': 'occurrence', 'id': 'two'}, 'timing': {}},
      ],
    }));
    expect(partial.comparisonRows, isEmpty);
    final foreign = DiscoveryN2Depth(possibility(family: 'funding_activity', wire: const {
      'variants': [
        {'occurrence': {'kind': 'occurrence', 'id': 'one'},
         'timing': {'start_date': '2026-11-12'}},
        {'occurrence': {'kind': 'occurrence', 'id': 'two'},
         'timing': {'start_date': '2026-11-13'}},
      ],
    }));
    expect(foreign.variants, isEmpty);
    expect(foreign.comparisonRows, isEmpty);
  });

  test('owner relations are not relabeled as alternatives', () {
    final depth = DiscoveryN2Depth(possibility(wire: const {
      'relations': [
        {'label': 'Peut aider à financer cette formation', 'type': 'complement'},
        {'type': 'alternative', 'target': {'kind': 'activity', 'id': 'other'}},
      ],
    }));
    expect(depth.relations, ['Peut aider à financer cette formation']);
    expect(depth.comparisonRows, isEmpty);
  });

  testWidgets('N2 renders real owner depth, assessment and dimension table', (
    tester,
  ) async {
    final item = possibility(wire: const {
      'assessment': [
        {'state': 'limiting', 'label': 'Places limitées'},
        {'state': 'unknown', 'label': 'Conditions non confirmées'},
      ],
      'variants': [
        {'occurrence': {'kind': 'occurrence', 'id': 'session-a'},
         'timing': {'start_date': '2026-11-12'}},
        {'occurrence': {'kind': 'occurrence', 'id': 'session-b'},
         'timing': {'start_date': '2026-11-13'}},
      ],
    });
    String? opened;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(390, 840),
      child: SingleChildScrollView(
        child: DiscoveryN2DepthSection(
          item: item, onOpenOccurrence: (id) => opened = id,
        ),
      ),
    );
    expect(find.text('Informations non établies'), findsOneWidget);
    expect(find.text('Conditions non confirmées'), findsOneWidget);
    expect(find.text('Places limitées'), findsOneWidget);
    expect(find.byKey(const Key('discover-n2-conditional-comparison')),
        findsOneWidget);
    expect(find.text('Variante 1'), findsWidgets);
    await tester.ensureVisible(
      find.byKey(const ValueKey('discover-n2-owner-occurrence-session-a')),
    );
    await tester.tap(
      find.byKey(const ValueKey('discover-n2-owner-occurrence-session-a')),
    );
    await tester.pump();
    expect(opened, 'session-a');
    expect(tester.takeException(), isNull);
  });
}
