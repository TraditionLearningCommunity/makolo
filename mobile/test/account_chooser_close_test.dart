import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/auth/auth_entry_frame.dart';

void main() {
  testWidgets('account selection frame offers an explicit close action', (
    tester,
  ) async {
    var closed = false;
    await tester.pumpWidget(
      MaterialApp(
        home: AuthEntryFrame(
          title: 'Choisir un compte',
          onClose: () => closed = true,
          child: const Text('Compte mémorisé'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byTooltip('Fermer'), findsOneWidget);
    await tester.tap(find.byTooltip('Fermer'));
    expect(closed, isTrue);
  });
}
