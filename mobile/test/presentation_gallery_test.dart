import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/dev/gallery/presentation_gallery.dart';

void main() {
  testWidgets('dev gallery runs without server and its core controls reflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const PresentationGalleryApp());
    await tester.pump();

    expect(find.text('Makolo Presentation Gallery'), findsOneWidget);
    expect(find.byKey(const Key('gallery-scenario')), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('gallery-theme-toggle')));
    await tester.pump();
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('gallery-viewport-cycle')));
    await tester.pump();
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('gallery-text-scale-cycle')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('gallery-text-scale-cycle')));
    await tester.pump();
    expect(find.text('Text 1.6'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('gallery-reduce-motion')));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
