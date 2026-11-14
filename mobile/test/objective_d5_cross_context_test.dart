import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  test('D5: same Dossier identity with isolated Space snapshots', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'member');
    final repository = ObjectiveRepository(
      database: db,
      store: store,
      profileId: 'member',
    );
    const id = 'dossier-canonical';
    const kind = ObjectiveRepository.dossierProjectionKind;

    for (final space in ['space-a', 'space-b']) {
      await store.putProjection(
        kind: kind,
        resourceKey: ObjectiveRepository.detailResourceKey(
          id,
          spaceSlug: space,
        ),
        schemaVersion: 1,
        payload: {
          'identity': {'kind': 'dossier', 'id': id},
          'actor_context': {
            'kind': 'space',
            'space': {'slug': space},
          },
          'owner': {'slug': space},
        },
      );
    }

    expect(await repository.read(ObjectiveDepth.dossier, id), isNull);
    final a = await repository.read(
      ObjectiveDepth.dossier,
      id,
      spaceSlug: 'space-a',
    );
    final b = await repository.read(
      ObjectiveDepth.dossier,
      id,
      spaceSlug: 'space-b',
    );
    expect(a?.payload['identity'], b?.payload['identity']);
    expect((a?.payload['owner'] as Map)['slug'], 'space-a');
    expect((b?.payload['owner'] as Map)['slug'], 'space-b');
    expect(
      repository
          .sourceFor(ObjectiveDepth.dossier, id, spaceSlug: 'space-a')
          .sourceKey,
      isNot(
        repository
            .sourceFor(ObjectiveDepth.dossier, id, spaceSlug: 'space-b')
            .sourceKey,
      ),
    );
  });

  test(
    'D5: detail, Project pagination and Organizer use same Space lens',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final repository = ObjectiveRepository(
        database: db,
        store: ProfileStore(db, 'member'),
        profileId: 'member',
      );
      const id = 'project-canonical';
      final personal = repository.sourceFor(ObjectiveDepth.project, id);
      final a = repository.sourceFor(
        ObjectiveDepth.project,
        id,
        spaceSlug: 'space-a',
      );
      final b = repository.sourceFor(
        ObjectiveDepth.project,
        id,
        spaceSlug: 'space-b',
      );
      expect(personal.path, isNot(contains('context=space')));
      expect(a.path, contains('?context=space&space=space-a'));
      expect(b.resourceKey, isNot(a.resourceKey));

      final aPage = repository.projectDossierSource(
        id,
        50,
        spaceSlug: 'space-a',
      );
      final bPage = repository.projectDossierSource(
        id,
        50,
        spaceSlug: 'space-b',
      );
      expect(aPage.path, contains('&context=space&space=space-a'));
      expect(aPage.resourceKey, isNot(bPage.resourceKey));
      expect(aPage.sourceKey, isNot(bPage.sourceKey));

      final aOrganizer = repository.organizerSourceFor(
        50,
        spaceSlug: 'space-a',
      );
      final bOrganizer = repository.organizerSourceFor(
        50,
        spaceSlug: 'space-b',
      );
      expect(aOrganizer.path, contains('&context=space&space=space-a'));
      expect(aOrganizer.resourceKey, isNot(bOrganizer.resourceKey));
      expect(aOrganizer.sourceKey, isNot(bOrganizer.sourceKey));
      expect(
        repository.organizerSourceFor(0).path,
        isNot(contains('context=space')),
      );
    },
  );
}
