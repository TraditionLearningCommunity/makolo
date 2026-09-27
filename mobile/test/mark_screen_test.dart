import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/mark/mark_screen.dart';

import 'fakes.dart';

void main() {
  testWidgets('Makolo Mark placeholder stays product-facing', (tester) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: MarkScreen(runtime: runtime),
      ),
    );

    expect(find.text('Qu’est-ce que vous avez en tête ?'), findsOneWidget);
    expect(find.textContaining('A1'), findsNothing);
    expect(find.textContaining('A2'), findsNothing);
    expect(find.byTooltip('Avatar'), findsOneWidget);
    expect(find.byTooltip('Notifications'), findsNothing);
  });
}
