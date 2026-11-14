import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/dossier_workspace_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  testWidgets('Dossier title, compact actions and views fit a small phone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'viewer');
    final repository = ObjectiveRepository(
      database: database,
      store: store,
      profileId: 'viewer',
    );
    await store.putProjection(
      kind: ObjectiveRepository.dossierProjectionKind,
      resourceKey: 'compact-dossier',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'compact-dossier'},
        'objective': {
          'title': 'Organiser les services essentiels et les priorités',
          'description': 'Un résultat concret à préparer.',
        },
        'owner': {'kind': 'profile', 'label': 'Dossier personnel'},
        'state': {'code': 'active'},
        'readiness': {'partial': false},
        'created_at': '2026-11-09T12:00:00Z',
        'updated_at': '2026-11-10T12:00:00Z',
        'visible_journeys_complete': true,
        'visible_journeys': [
          {'id': 'journey-1', 'label': 'Première démarche', 'state': 'draft'},
        ],
        'visible_dependencies': [],
        'assignments': [],
        'mandates': [],
        'capabilities': ['dossier.edit', 'dossier.journey.link'],
      },
    );

    await tester.pumpWidget(
      MaterialApp(
        home: DossierWorkspaceScreen(
          id: 'compact-dossier',
          repository: repository,
          onOpenJourney: (_) {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(find.text('Explorer le Dossier'), findsNothing);
    expect(find.text('Lier une démarche'), findsNothing);
    // Without a connected action owner, avoid a disabled, misleading CTA.
    expect(find.text('Lier'), findsNothing);
    expect(find.byTooltip('Informations du Dossier'), findsOneWidget);
    final topbarMenu = find.descendant(
      of: find.byType(AppBar),
      matching: find.byIcon(Icons.more_horiz_rounded),
    );
    expect(topbarMenu, findsOneWidget);
    expect(tester.takeException(), isNull);

    final info = find.byTooltip('Informations du Dossier');
    await tester.ensureVisible(info);
    await tester.tap(info);
    await tester.pumpAndSettle();
    expect(find.text('Créé le'), findsOneWidget);
    expect(find.text('Mis à jour le'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('View controls are adjacent to journeys, not a footer', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'viewer');
    final repository = ObjectiveRepository(
      database: database,
      store: store,
      profileId: 'viewer',
    );
    await store.putProjection(
      kind: ObjectiveRepository.dossierProjectionKind,
      resourceKey: 'compact-switcher',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'compact-switcher'},
        'objective': {'title': 'Dossier et démarches'},
        'owner': {'kind': 'profile', 'label': 'Personnel'},
        'state': {'code': 'active'},
        'readiness': {'partial': false},
        'visible_journeys_complete': true,
        'visible_journeys': [
          {'id': 'journey-2', 'label': 'Démarche liée', 'state': 'draft'},
        ],
        'visible_dependencies': [],
        'assignments': [],
        'mandates': [],
        'capabilities': [],
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: DossierWorkspaceScreen(
          id: 'compact-switcher',
          repository: repository,
          onOpenJourney: (_) {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(find.byTooltip('Vue d’ensemble'), findsOneWidget);
    expect(find.byTooltip('Liste'), findsOneWidget);
    await tester.ensureVisible(find.byTooltip('Liste'));
    await tester.tap(find.byTooltip('Liste'));
    await tester.pump();
    expect(find.text('Explorer le Dossier'), findsNothing);
    // Detailed lists start under the AppBar, not below the whole Dossier.
    expect(find.text('Dossier et démarches'), findsNothing);
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byTooltip('Vue d’ensemble'), findsOneWidget);
    expect(
      tester.getSize(find.byTooltip('Liste')).width,
      lessThanOrEqualTo(44),
    );
    expect(tester.takeException(), isNull);
  });
}
