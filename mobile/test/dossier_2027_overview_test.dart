import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/dossier_workspace_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  testWidgets(
    'Dossier overview shows real people, a next action and linked Journeys',
    (tester) async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'viewer');
      final repo = ObjectiveRepository(
        database: db,
        store: store,
        profileId: 'viewer',
      );
      await store.putProjection(
        kind: ObjectiveRepository.dossierProjectionKind,
        resourceKey: 'dossier-a',
        schemaVersion: 1,
        payload: {
          'identity': {'kind': 'dossier', 'id': 'dossier-a'},
          'objective': {'title': 'Objectif concret', 'description': 'Préparer'},
          'owner': {'kind': 'profile', 'label': 'Dossier personnel'},
          'state': {'code': 'active'},
          'readiness': {
            'state': 'action_required',
            'label': 'Action requise',
            'partial': false,
            'next_action': {
              'label': 'Continuer la démarche',
              'journey_id': 'j-1',
            },
          },
          'visible_journeys_complete': true,
          'visible_journeys': [
            {'id': 'j-1', 'label': 'Démarche une', 'state': 'fulfilled'},
            {
              'id': 'j-2',
              'label': 'Démarche deux',
              'state': 'draft',
              'readiness_state': 'action_required',
            },
          ],
          'visible_dependencies': [],
          'assignments': [
            {
              'id': 'assignment',
              'label': 'Alice',
              'profile_id': 'profile-alice',
              'profile_url': '/people/profile-alice',
            },
          ],
          'mandates': [],
          'people_preview': {
            'people': [
              {
                'profile_id': 'profile-alice',
                'label': 'Alice',
                'profile_url': '/people/profile-alice',
              },
            ],
            'remaining': 0,
          },
          'capabilities': [],
        },
      );
      String? openedProfile;
      String? openedJourney;
      var openedPeople = false;
      await tester.pumpWidget(
        MaterialApp(
          home: DossierWorkspaceScreen(
            id: 'dossier-a',
            repository: repo,
            onOpenJourney: (id) => openedJourney = id,
            onOpenPerson: (id) => openedProfile = id,
            onOpenPeople: () => openedPeople = true,
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      expect(find.text('Objectif concret'), findsOneWidget);
      expect(find.text('Personnes et responsabilités'), findsOneWidget);
      expect(find.text('À faire maintenant'), findsOneWidget);
      expect(find.text('1 sur 2 démarches visibles terminées'), findsOneWidget);
      await tester.ensureVisible(find.byType(CircleAvatar).first);
      await tester.tap(find.byType(CircleAvatar).first);
      expect(openedProfile, 'profile-alice');
      final peopleLink = find.text('Personnes et responsabilités');
      await tester.ensureVisible(peopleLink);
      await tester.tap(peopleLink);
      expect(openedPeople, isTrue);
      await tester.ensureVisible(find.text('Démarche une').first);
      await tester.tap(find.text('Démarche une').first);
      expect(openedJourney, 'j-1');
      await tester.ensureVisible(find.text('1 à traiter'));
      await tester.tap(find.text('1 à traiter'));
      await tester.pump();
      expect(find.text('Démarche deux'), findsOneWidget);
      expect(find.text('Démarche une'), findsNothing);
    },
  );

  testWidgets('Partial local data is not presented as an empty Dossier', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'viewer');
    final repo = ObjectiveRepository(
      database: db,
      store: store,
      profileId: 'viewer',
    );
    await store.putProjection(
      kind: ObjectiveRepository.dossierProjectionKind,
      resourceKey: 'dossier-partial',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'dossier-partial'},
        'objective': {'title': 'Dossier à synchroniser'},
        'owner': {'kind': 'profile', 'label': 'Personnel'},
        'state': {'code': 'active'},
        'readiness': {'partial': true},
        'visible_journeys_complete': false,
        'visible_journeys': [],
        'visible_dependencies': [],
        'assignments': [],
        'mandates': [],
        'capabilities': [],
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: DossierWorkspaceScreen(
          id: 'dossier-partial',
          repository: repo,
          onOpenJourney: (_) {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(
      find.text('Aucune démarche disponible dans les données acquises.'),
      findsOneWidget,
    );
    expect(find.text('Aucune démarche visible.'), findsNothing);
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });

  testWidgets('Empty Dossier avoids invented progress and keeps simple state', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'viewer');
    final repo = ObjectiveRepository(
      database: db,
      store: store,
      profileId: 'viewer',
    );
    await store.putProjection(
      kind: ObjectiveRepository.dossierProjectionKind,
      resourceKey: 'dossier-empty',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'dossier-empty'},
        'objective': {'title': 'Dossier vide'},
        'owner': {'kind': 'profile', 'label': 'Personnel'},
        'state': {'code': 'draft'},
        'readiness': {'partial': false},
        'visible_journeys_complete': true,
        'visible_journeys': [],
        'visible_dependencies': [],
        'assignments': [],
        'mandates': [],
        'capabilities': [],
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: DossierWorkspaceScreen(
          id: 'dossier-empty',
          repository: repo,
          onOpenJourney: (_) {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Dossier vide'), findsOneWidget);
    expect(find.text('Aucune démarche visible.'), findsOneWidget);
    expect(find.textContaining('sur 0 démarches'), findsNothing);
    expect(find.text('Personnes et responsabilités'), findsNothing);
  });
}
