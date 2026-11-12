import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/dossier_people_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  testWidgets('Dossier people only shows projected responsibilities and mandates', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'viewer');
    final repo = ObjectiveRepository(
      database: db, store: store, profileId: 'viewer',
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
  });

  testWidgets('Read-only projection does not invent hidden colleagues', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'viewer');
    final repo = ObjectiveRepository(
      database: db, store: store, profileId: 'viewer',
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
}
