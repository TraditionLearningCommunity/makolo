import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/design/presentation_layout.dart';

import 'support/presentation_harness.dart';

void main() {
  test('classifies Presentation widths without changing shell geometry', () {
    expect(MakoloLayout.widthClassFor(359), MakoloWidthClass.compact);
    expect(MakoloLayout.widthClassFor(720), MakoloWidthClass.medium);
    expect(MakoloLayout.widthClassFor(960), MakoloWidthClass.wide);
    expect(MakoloLayout.widthClassFor(1440), MakoloWidthClass.veryWide);
    expect(MakoloLayout.navigationRailMinWidth, 840);
  });

  test('split requires both geometric minima and the surface threshold', () {
    expect(
      MakoloLayout.canSplit(
        availableWidth: 920,
        splitAt: MakoloLayout.ongoingSplitMinWidth,
      ),
      isFalse,
    );
    expect(
      MakoloLayout.canSplit(
        availableWidth: 960,
        splitAt: MakoloLayout.ongoingSplitMinWidth,
      ),
      isTrue,
    );
    expect(
      MakoloLayout.canSplit(
        availableWidth: 700,
        fieldMin: 400,
        focusMin: 400,
        gutter: 24,
        splitAt: 600,
      ),
      isFalse,
    );
  });

  test('Jour J participant uses the Golden v1.1 880dp candidate boundary', () {
    expect(
      MakoloLayout.canSplit(
        availableWidth: 840,
        fieldMin: MakoloLayout.dayOfActionMinWidth,
        focusMin: MakoloLayout.focusMinWidth,
        splitAt: MakoloLayout.dayOfParticipantSplitMinWidth,
      ),
      isFalse,
    );
    expect(
      MakoloLayout.canSplit(
        availableWidth: 880,
        fieldMin: MakoloLayout.dayOfActionMinWidth,
        focusMin: MakoloLayout.focusMinWidth,
        splitAt: MakoloLayout.dayOfParticipantSplitMinWidth,
      ),
      isTrue,
    );
  });

  test('resolved split protects Field and Focus minima', () {
    final geometry = MakoloSplitGeometry.resolve(
      availableWidth: 960,
      splitAt: MakoloLayout.ongoingSplitMinWidth,
    );

    expect(geometry.split, isTrue);
    expect(
      geometry.fieldWidth,
      greaterThanOrEqualTo(MakoloLayout.fieldMinWidth),
    );
    expect(
      geometry.focusWidth,
      greaterThanOrEqualTo(MakoloLayout.focusMinWidth),
    );
    expect(
      geometry.focusWidth,
      lessThanOrEqualTo(MakoloLayout.focusMaxWidth),
    );
  });

  testWidgets('adaptive split stays single below threshold and splits at it', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(920, 800),
      child: const MakoloAdaptiveSplit(
        splitAt: MakoloLayout.ongoingSplitMinWidth,
        field: Text('Field'),
        focus: Text('Focus'),
      ),
    );
    expect(
      find.byKey(const Key('makolo-adaptive-split-single')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsNothing);

    await PresentationHarness.pump(
      tester,
      viewport: const Size(960, 800),
      child: const MakoloAdaptiveSplit(
        splitAt: MakoloLayout.ongoingSplitMinWidth,
        field: Text('Field'),
        focus: Text('Focus'),
      ),
    );
    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
  });

  testWidgets('content frame caps readable content width', (tester) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1200, 800),
      child: const MakoloContentFrame(
        maxContentWidth: MakoloLayout.readingMaxWidth,
        child: SizedBox(height: 100),
      ),
    );

    final size = tester.getSize(
      find.byKey(const Key('makolo-content-frame-body')),
    );
    expect(size.width, MakoloLayout.readingMaxWidth);
  });
}
