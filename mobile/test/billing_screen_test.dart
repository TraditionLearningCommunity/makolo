import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/settings/billing_screen.dart';

void main() {
  testWidgets('billing stays human and does not invent commercial data', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));

    expect(find.text('Abonnement & facturation'), findsOneWidget);
    expect(
      find.text('Aucun abonnement ou élément de facturation pour le moment.'),
      findsOneWidget,
    );
    expect(find.textContaining('provider'), findsNothing);
    expect(find.textContaining('capacité réelle'), findsNothing);
    expect(find.textContaining('prix'), findsNothing);
  });
}
