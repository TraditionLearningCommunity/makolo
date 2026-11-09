import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/identity_surface.dart';

void main() {
  testWidgets(
    'identity portrait accepts either owner identity without a domain dependency',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MakoloIdentityPortrait(
              name: 'Collectif témoin',
              eyebrow: 'Organisation',
              subtitle: 'Mission collective',
              leading: Icon(Icons.apartment_rounded),
            ),
          ),
        ),
      );
      expect(find.text('Collectif témoin'), findsOneWidget);
      expect(find.text('Mission collective'), findsOneWidget);
      expect(find.byIcon(Icons.apartment_rounded), findsOneWidget);
    },
  );

  testWidgets('Space can bound its summary without truncating Moi by default', (
    tester,
  ) async {
    const summary =
        'Un collectif qui accompagne de nombreux projets et '
        'rencontres dans plusieurs quartiers du territoire.';
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              MakoloIdentityPortrait(
                name: 'Moi',
                leading: Icon(Icons.person_outline),
                subtitle: summary,
              ),
              MakoloIdentityPortrait(
                name: 'Notre collectif',
                leading: Icon(Icons.apartment_rounded),
                subtitle: summary,
                subtitleMaxLines: 2,
              ),
            ],
          ),
        ),
      ),
    );
    final summaries = tester
        .widgetList<Text>(find.text(summary))
        .toList(growable: false);
    expect(summaries.length, 2);
    expect(summaries.first.maxLines, isNull);
    expect(summaries.last.maxLines, 2);
    expect(summaries.last.data, summary);
  });

  testWidgets('Passport gateway opens only an owner supplied action', (
    tester,
  ) async {
    var opens = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              MakoloPassportGateway(
                title: 'Mon passeport',
                subtitle: 'Profil',
                onOpen: () => opens++,
              ),
              const MakoloPassportGateway(
                title: 'Passeport de cet Espace',
                subtitle: 'Collectif',
                onOpen: null,
              ),
            ],
          ),
        ),
      ),
    );
    await tester.tap(find.text('Mon passeport'));
    expect(opens, 1);
    expect(find.text('Passeport de cet Espace'), findsOneWidget);
    final blocked = tester.widget<InkWell>(
      find
          .ancestor(
            of: find.text('Passeport de cet Espace'),
            matching: find.byType(InkWell),
          )
          .first,
    );
    expect(blocked.onTap, isNull);
  });

  testWidgets('primary shortcut preserves the explicit owner callback', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MakoloPrimaryShortcut(
            title: 'Mes démarches',
            subtitle: 'Projets et dossiers',
            icon: Icons.folder_outlined,
            onOpen: () => calls++,
          ),
        ),
      ),
    );
    await tester.tap(find.text('Mes démarches'));
    expect(calls, 1);
  });

  testWidgets(
    'shared list never fabricates previews beyond the bounded window',
    (tester) async {
      var opens = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MakoloTerritoryListCard(
              title: 'Nos ressources',
              subtitle: 'Documents visibles',
              symbol: const Icon(Icons.folder_outlined),
              onOpen: () => opens++,
              previews: const [
                MakoloTerritoryPreview(title: 'Document 1'),
                MakoloTerritoryPreview(title: 'Document 2'),
                MakoloTerritoryPreview(title: 'Document 3'),
                MakoloTerritoryPreview(title: 'Document 4'),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Document 1'), findsOneWidget);
      expect(find.text('Document 3'), findsOneWidget);
      expect(find.text('Document 4'), findsNothing);
      await tester.tap(find.text('Nos ressources'));
      expect(opens, 1);
    },
  );

  testWidgets(
    'view toggle exposes list and grid without reading actor permissions',
    (tester) async {
      var choice = MakoloTerritoryLayout.list;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MakoloTerritoryViewToggle(
              value: choice,
              onChanged: (value) => choice = value,
            ),
          ),
        ),
      );
      await tester.tap(find.byIcon(Icons.grid_view_rounded));
      expect(choice, MakoloTerritoryLayout.grid);
    },
  );
}
