import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/dossier_workspace_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  testWidgets('Visible people overflow opens the owner-backed full list', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'viewer');
    final repository = ObjectiveRepository(
      database: db,
      store: store,
      profileId: 'viewer',
    );
    final people = List.generate(
      5,
      (i) => {
        'label': 'Personne ' + (i + 1).toString(),
        'profile_id': 'profile-' + i.toString(),
      },
    );
    await store.putProjection(
      kind: ObjectiveRepository.dossierProjectionKind,
      resourceKey: 'dossier-five',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'dossier-five'},
        'objective': {'title': 'Dossier collectif'},
        'owner': {'kind': 'space', 'label': 'Espace collectif'},
        'state': {'code': 'active'},
        'readiness': {'partial': false},
        'visible_journeys_complete': true,
        'visible_journeys': [],
        'visible_dependencies': [],
        'assignments': [
          for (final person in people)
            {
              'id': person['profile_id'],
              'label': person['label'],
              'profile_id': person['profile_id'],
            },
        ],
        'mandates': [],
        'people_preview': {'people': people.take(4).toList(), 'remaining': 1},
        'capabilities': [],
      },
    );

    var fullListOpened = 0;
    String? personId;
    await tester.pumpWidget(
      MaterialApp(
        home: DossierWorkspaceScreen(
          id: 'dossier-five',
          repository: repository,
          onOpenJourney: (_) {},
          onOpenPeople: () => fullListOpened++,
          onOpenPerson: (id) => personId = id,
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    expect(find.text('Personnes et responsabilités'), findsOneWidget);
    expect(find.text('+1'), findsOneWidget);
    await tester.ensureVisible(find.text('+1'));
    await tester.tap(find.text('+1'));
    expect(fullListOpened, 1);

    await tester.ensureVisible(find.byType(CircleAvatar).first);
    await tester.tap(find.byType(CircleAvatar).first);
    expect(personId, 'profile-0');
  });

  testWidgets('Waived Dossier dependency is not labeled unsatisfied', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'viewer');
    final repository = ObjectiveRepository(
      database: db,
      store: store,
      profileId: 'viewer',
    );
    await store.putProjection(
      kind: ObjectiveRepository.dossierProjectionKind,
      resourceKey: 'dossier-waived',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'dossier-waived'},
        'objective': {'title': 'Dossier avec condition'},
        'owner': {'kind': 'profile', 'label': 'Personnel'},
        'state': {'code': 'active'},
        'readiness': {'partial': false},
        'visible_journeys_complete': true,
        'visible_journeys': [],
        'visible_dependencies': [
          {
            'id': 'dependency-waived',
            'state': 'waived',
            'satisfied': false,
            'required_label': 'Démarche préalable',
          },
        ],
        'assignments': [],
        'mandates': [],
        'capabilities': [],
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: DossierWorkspaceScreen(
          id: 'dossier-waived',
          repository: repository,
          onOpenJourney: (_) {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));

    await tester.ensureVisible(find.text('Conditions et dépendances'));
    await tester.tap(find.text('Conditions et dépendances'));
    await tester.pumpAndSettle();
    expect(find.text('Condition levée'), findsOneWidget);
    expect(find.text('À satisfaire'), findsNothing);
  });
}
