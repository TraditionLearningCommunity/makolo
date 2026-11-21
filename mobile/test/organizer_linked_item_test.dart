import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/organizer_linked_item.dart';

void main() {
  testWidgets('owner-backed child is a real clickable element', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OrganizerLinkedItem(
            title: 'Dossier de partenariat',
            kind: 'Dossier',
            icon: Icons.folder_outlined,
            onOpen: () => calls++,
          ),
        ),
      ),
    );

    expect(find.text('Dossier de partenariat'), findsOneWidget);
    expect(find.text('Dossier'), findsOneWidget);
    expect(find.byIcon(Icons.chevron_right_rounded), findsOneWidget);
    await tester.tap(find.text('Dossier de partenariat'));
    expect(calls, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('long linked item remains readable on a narrow phone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(16),
            child: OrganizerLinkedItem(
              title: 'Démarche de coordination du projet collectif',
              kind: 'Démarche',
              icon: Icons.route_outlined,
              onOpen: () {},
              dense: true,
            ),
          ),
        ),
      ),
    );
    expect(find.textContaining('Démarche de coordination'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
