import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/dev/scenarios/now_scenarios.dart';

Future<void> pumpNowGolden(
  WidgetTester tester, {
  required String scenario,
  required double textScale,
}) async {
  tester.view.physicalSize = const Size(360, 800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  await tester.pumpWidget(
    MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildMakoloLightTheme(),
      home: MediaQuery(
        data: MediaQueryData(
          size: const Size(360, 800),
          textScaler: TextScaler.linear(textScale),
        ),
        child: Scaffold(
          body: RepaintBoundary(
            key: const Key('now-golden-root'),
            child: NowGalleryScenarioPreview(id: scenario),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  const architectures = ['s1', 's2', 's3', 's4', 's5'];
  const variants = ['min', 'rich'];

  for (final architecture in architectures) {
    for (final variant in variants) {
      final id = 'now-g01-$architecture-$variant';
      testWidgets('G01 $architecture $variant golden at 360px', (tester) async {
        await pumpNowGolden(tester, scenario: id, textScale: 1);
        await expectLater(
          find.byKey(const Key('now-golden-root')),
          matchesGoldenFile('goldens/now/$architecture-$variant-100.png'),
        );
      }, tags: 'golden');
    }

    for (final scale in [1.3, 1.6]) {
      final id = 'now-g01-$architecture-min';
      final name = scale == 1.3 ? '130' : '160';
      testWidgets('G01 $architecture minimum at text scale $scale', (
        tester,
      ) async {
        await pumpNowGolden(tester, scenario: id, textScale: scale);
        await expectLater(
          find.byKey(const Key('now-golden-root')),
          matchesGoldenFile('goldens/now/$architecture-min-$name.png'),
        );
      }, tags: 'golden');
    }
  }
}
