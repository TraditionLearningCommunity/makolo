import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/mark/mark_screen.dart';

void main() {
  testWidgets('Makolo Mark placeholder stays product-facing', (tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: buildMakoloTheme(), home: const MarkScreen()),
    );

    expect(find.text('Qu’est-ce que vous avez en tête ?'), findsOneWidget);
    expect(find.textContaining('A1'), findsNothing);
    expect(find.textContaining('A2'), findsNothing);
  });
}
