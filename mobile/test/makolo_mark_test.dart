import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_mark.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  Widget wrap(Widget child) => MaterialApp(
    theme: buildMakoloLightTheme(),
    darkTheme: buildMakoloDarkTheme(),
    home: Scaffold(body: Center(child: child)),
  );

  testWidgets('Makolo Mark remains informative by default', (tester) async {
    await tester.pumpWidget(wrap(const MakoloMark()));

    expect(find.bySemanticsLabel('Makolo'), findsOneWidget);
  });

  testWidgets('structural Mark keeps a single Makolo semantic node', (
    tester,
  ) async {
    await tester.pumpWidget(
      wrap(const MakoloMark(semantics: MakoloMarkSemantics.structural)),
    );

    expect(find.bySemanticsLabel('Makolo'), findsOneWidget);
  });

  testWidgets('decorative Mark is excluded from semantics', (tester) async {
    await tester.pumpWidget(
      wrap(const MakoloMark(semantics: MakoloMarkSemantics.decorative)),
    );

    expect(find.bySemanticsLabel('Makolo'), findsNothing);
  });
}
