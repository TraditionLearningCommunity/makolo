import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/auth/auth_entry_frame.dart';

void main() {
  testWidgets(
    'compact account chooser keeps a real close button above identity',
    (tester) async {
      var closed = false;
      await tester.pumpWidget(
        MaterialApp(
          home: AuthEntryFrame(
            title: 'Choisir un compte',
            compactIdentity: true,
            onClose: () => closed = true,
            child: const Text('Compte mémorisé'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final close = find.byKey(const Key('account-chooser-close'));
      expect(close, findsOneWidget);
      final mark = find.text('Choisir un compte');
      expect(tester.getTopLeft(close).dy, lessThan(tester.getTopLeft(mark).dy));
      expect(tester.getSize(close).width, greaterThanOrEqualTo(48));
      await tester.tap(close);
      expect(closed, isTrue);
    },
  );

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
