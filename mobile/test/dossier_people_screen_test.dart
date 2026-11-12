import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/dossier_people_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  testWidgets(
    'Dossier people only shows projected responsibilities and mandates',
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
        resourceKey: 'dossier-with-people',
        schemaVersion: 1,
        payload: {
          'identity': {'kind': 'dossier', 'id': 'dossier-with-people'},
          'objective': {'title': 'Un résultat à coordonner'},
          'owner': {'kind': 'space', 'label': 'Collectif A'},
          'assignments': [
            {
              'id': 'a1',
              'label': 'Alice',
              'profile_id': 'alice-profile',
              'profile_url': '/people/alice-profile',
            },
          ],
          'mandates': [
            {
              'id': 'm1',
              'profile': 'Bob',
              'profile_id': 'bob-profile',
              'role': 'Gestionnaire',
            },
          ],
        },
      );
      String? selected;
      await tester.pumpWidget(
        MaterialApp(
          home: DossierPeopleScreen(
            id: 'dossier-with-people',
            repository: repo,
            onOpenPerson: (id) => selected = id,
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      expect(find.text('Coordination'), findsOneWidget);
      expect(find.text('Autorisations'), findsOneWidget);
      expect(find.text('Porteur du Dossier'), findsOneWidget);
      expect(find.text('Alice'), findsOneWidget);
      expect(find.text('Bob'), findsOneWidget);
      await tester.ensureVisible(find.text('Alice'));
      await tester.tap(find.text('Alice'));
      expect(selected, 'alice-profile');

      // Bob's Mandate is visible, but his private Profile is not a link.
      selected = null;
      await tester.ensureVisible(find.text('Bob'));
      await tester.tap(find.text('Bob'));
      expect(selected, isNull);
    },
  );

  testWidgets('Read-only projection does not invent hidden colleagues', (
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
      resourceKey: 'dossier-private',
      schemaVersion: 1,
      payload: {
        'identity': {'kind': 'dossier', 'id': 'dossier-private'},
        'objective': {'title': 'Dossier privé'},
        'owner': {'kind': 'profile', 'label': 'Personnel'},
        'assignments': [],
        'mandates': [],
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: DossierPeopleScreen(
          id: 'dossier-private',
          repository: repo,
          onOpenPerson: (_) {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Aucune responsabilité visible'), findsOneWidget);
    expect(find.text('Aucun mandat visible dans ce contexte'), findsOneWidget);
    expect(find.byType(CircleAvatar), findsNothing);
  });

  testWidgets(
    'Own Dossier responsibility opens personal Passport, not public view',
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
        resourceKey: 'dossier-self',
        schemaVersion: 1,
        payload: {
          'identity': {'kind': 'dossier', 'id': 'dossier-self'},
          'objective': {'title': 'Ma coordination'},
          'owner': {'kind': 'profile', 'label': 'Personnel'},
          'assignments': [
            {
              'id': 'self-assignment',
              'label': 'Vous',
              'profile_id': 'viewer',
              'profile_url': '/me/passport',
              'profile_view': 'self',
            },
          ],
          'mandates': [],
        },
      );
      String? openedPublic;
      var openedSelf = false;
      await tester.pumpWidget(
        MaterialApp(
          home: DossierPeopleScreen(
            id: 'dossier-self',
            repository: repo,
            onOpenPerson: (id) => openedPublic = id,
            onOpenMyPassport: () => openedSelf = true,
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      await tester.ensureVisible(find.text('Vous'));
      await tester.tap(find.text('Vous'));
      expect(openedSelf, isTrue);
      expect(openedPublic, isNull);
    },
  );
}
