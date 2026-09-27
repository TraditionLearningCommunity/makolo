import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_mark.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/splash/brand_moment.dart';

void main() {
  testWidgets('brand moment uses footsteps then the canonical Mark', (
    tester,
  ) async {
    var finished = false;

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: BrandMoment(onFinished: () => finished = true),
      ),
    );

    expect(find.byKey(const Key('brand-footsteps')), findsOneWidget);
    expect(find.byType(MakoloMark), findsOneWidget);

    await tester.pump(const Duration(seconds: 1));

    expect(finished, isTrue);
  });

  testWidgets('Reduce Motion uses a short static Mark variant', (tester) async {
    var finished = false;

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: BrandMoment(onFinished: () => finished = true),
        ),
      ),
    );

    expect(find.byType(MakoloMark), findsOneWidget);
    expect(find.byKey(const Key('brand-footsteps')), findsNothing);

    await tester.pump(MakoloMotion.short);

    expect(finished, isTrue);
  });
}
