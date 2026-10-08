import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/dev/scenarios/now_scenarios.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';

import 'support/presentation_harness.dart';

void main() {
  test('S2 Gallery uses the actual Now media topology', () {
    final situation = NowGalleryScenarios.select('now-media').situations.single;
    expect(topologyFor(situation), NowTopology.media);
  });

  test('S4 Gallery is a real explicit waiting response', () {
    final situation = NowGalleryScenarios.select(
      'now-legitimate-waiting',
    ).situations.single;
    expect(topologyFor(situation), NowTopology.waiting);
  });

  test('S5 Gallery is a justified composition', () {
    final situation = NowGalleryScenarios.select(
      'now-multiple',
    ).situations.single;
    expect(topologyFor(situation), NowTopology.composition);
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
