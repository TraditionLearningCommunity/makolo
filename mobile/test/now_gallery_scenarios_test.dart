import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/dev/scenarios/now_scenarios.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';

import 'support/presentation_harness.dart';

void main() {
  test('G01 fixtures select five distinct real Now architectures', () {
    const expected = <String, NowTopology>{
      'now-g01-s1-min': NowTopology.meaning,
      'now-g01-s2-min': NowTopology.media,
      'now-g01-s3-min': NowTopology.action,
      'now-g01-s4-min': NowTopology.waiting,
      'now-g01-s5-min': NowTopology.composition,
    };
    for (final scenario in expected.entries) {
      final minimum = NowGalleryScenarios.select(scenario.key);
      final richer = NowGalleryScenarios.select(
        scenario.key.replaceFirst('-min', '-rich'),
      );
      expect(
        topologyFor(minimum.situations.single),
        scenario.value,
        reason: scenario.key,
      );
      expect(
        topologyFor(richer.situations.single),
        scenario.value,
        reason: '${scenario.key} rich',
      );
    }
  });

  for (final architecture in ['s1', 's2', 's3', 's4', 's5']) {
    for (final scale in [1.0, 1.3, 1.6]) {
      testWidgets('G01 $architecture compact renders at text scale $scale', (
        tester,
      ) async {
        await PresentationHarness.pump(
          tester,
          viewport: const Size(360, 800),
          textScale: scale,
          child: NowGalleryScenarioPreview(id: 'now-g01-$architecture-min'),
        );
        expect(tester.takeException(), isNull);
        expect(find.byType(NowView), findsOneWidget);
      });
    }
  }

  test('S2 Gallery uses the actual Now media topology', () {
    final situation = NowGalleryScenarios.select('now-media').situations.single;
    expect(topologyFor(situation), NowTopology.media);
  });

  test('S4 Gallery is a real explicit waiting response', () {
    final situation = NowGalleryScenarios.select('now-legitimate-waiting')
        .situations
        .single;
    expect(topologyFor(situation), NowTopology.waiting);
  });

  test('S5 Gallery is a justified composition', () {
    final situation = NowGalleryScenarios.select('now-multiple')
        .situations
        .single;
    expect(topologyFor(situation), NowTopology.composition);
  });

  testWidgets('G01 S3 action handoff uses production CTA with no mutation', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: const NowGalleryScenarioPreview(id: 'now-g01-s3-min'),
    );
    expect(
      find.widgetWithText(FilledButton, 'Vérifier le dossier'),
      findsOneWidget,
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Vérifier le dossier'));
    await tester.pump();
    expect(
      find.text('Démonstration : aucune action métier exécutée.'),
      findsOneWidget,
    );
    expect(find.text('Confirmé'), findsNothing);
  });

  testWidgets('Gallery scenario calm is not a fake empty loading state', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: const NowGalleryScenarioPreview(id: 'now-calm'),
    );
    expect(find.text('Tout est en ordre. ✓'), findsOneWidget);
  });

  testWidgets('Gallery S2 shows actual framed media presentation', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: const NowGalleryScenarioPreview(id: 'now-media'),
    );
    expect(find.text('Document de démonstration'), findsOneWidget);
  });

  testWidgets('Gallery N2 opens the same real Now depth on wide', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1440, 900),
      child: const NowGalleryScenarioPreview(id: 'now-n2'),
    );
    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
  });
}
