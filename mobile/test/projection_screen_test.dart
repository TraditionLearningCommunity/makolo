import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/personal/projection_screen.dart';

StoredProjection _projection({
  List<Object> items = const [
    {'label': 'Préparer le rendez-vous'},
  ],
}) {
  return StoredProjection(
    kind: 'personal.now',
    schemaVersion: 1,
    payload: {'items': items},
    receivedAt: DateTime.utc(2026, 9, 26),
  );
}

void main() {
  testWidgets('screen renders the local projection without HTTP', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProjectionScreen(
          title: 'Maintenant',
          stream: Stream.value(_projection()),
          emptyMessage: 'Tout est en ordre. ✓',
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Préparer le rendez-vous'), findsOneWidget);
    expect(find.text('Disponible sur cet appareil'), findsOneWidget);
    expect(find.textContaining('Projection locale'), findsNothing);
  });

  testWidgets('initial loading uses a skeleton then preserves real content', (
    tester,
  ) async {
    final controller = StreamController<StoredProjection?>();

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProjectionScreen(
          title: 'Maintenant',
          stream: controller.stream,
          emptyMessage: 'Tout est en ordre. ✓',
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(MakoloSkeleton), findsOneWidget);

    controller.add(_projection());
    await tester.pump();
    await tester.pump();

    expect(find.byType(MakoloSkeleton), findsNothing);
    expect(find.text('Préparer le rendez-vous'), findsOneWidget);

    await controller.close();
  });

  testWidgets('known empty Now becomes Tout est en ordre', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProjectionScreen(
          title: 'Maintenant',
          stream: Stream.value(_projection(items: const [])),
          emptyMessage: 'Tout est en ordre. ✓',
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Tout est en ordre. ✓'), findsOneWidget);
  });
}
