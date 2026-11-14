import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/objective_filter_reset.dart';

void main() {
  testWidgets('Shared reset remains hidden with default filters', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ObjectiveFilterReset(active: false, onClear: () {}),
        ),
      ),
    );
    expect(find.text('Tout effacer'), findsNothing);
  });

  testWidgets('Shared reset invokes the owning screen only on demand', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ObjectiveFilterReset(active: true, onClear: () => calls++),
        ),
      ),
    );
    await tester.tap(find.text('Tout effacer'));
    expect(calls, 1);
  });
}
