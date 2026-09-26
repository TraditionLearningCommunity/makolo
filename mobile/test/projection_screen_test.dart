import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/personal/projection_screen.dart';

void main() {
  testWidgets('screen renders the local projection without HTTP', (
    tester,
  ) async {
    final projection = StoredProjection(
      kind: 'personal.now',
      schemaVersion: 1,
      payload: {
        'items': [
          {'label': 'Préparer le rendez-vous'},
        ],
      },
      receivedAt: DateTime.utc(2026, 9, 26),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProjectionScreen(
          title: 'Maintenant',
          stream: Stream.value(projection),
          emptyMessage: 'Tout est en ordre. ✓',
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Préparer le rendez-vous'), findsOneWidget);
    expect(
      find.textContaining('Projection locale synchronisée'),
      findsOneWidget,
    );
  });

  testWidgets('known empty Now becomes Tout est en ordre', (tester) async {
    final projection = StoredProjection(
      kind: 'personal.now',
      schemaVersion: 1,
      payload: {'items': <Object>[]},
      receivedAt: DateTime.utc(2026, 9, 26),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProjectionScreen(
          title: 'Maintenant',
          stream: Stream.value(projection),
          emptyMessage: 'Tout est en ordre. ✓',
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Tout est en ordre. ✓'), findsOneWidget);
  });
}
