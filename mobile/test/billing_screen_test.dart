import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';

import 'fakes.dart';
import 'package:makolo_mobile/features/settings/billing_screen.dart';

void main() {
  testWidgets('billing stays human and does not invent commercial data', (
    tester,
  ) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );
    await tester.pumpWidget(MaterialApp(home: BillingScreen(runtime: runtime)));
    await tester.pumpAndSettle();

    expect(find.text('Abonnement & facturation'), findsOneWidget);
    expect(
      find.text('Aucune information fiable n’est disponible pour le moment.'),
      findsOneWidget,
    );
    expect(find.textContaining('provider'), findsNothing);
    expect(find.textContaining('capacité réelle'), findsNothing);
    expect(find.textContaining('prix'), findsNothing);
  });
}
