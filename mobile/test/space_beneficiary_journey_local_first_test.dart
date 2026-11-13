import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_artifact_repository.dart';

void main() {
  test('Space Journey and artifacts never share a personal identity key', () {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final repo = JourneyArtifactRepository(
      database: database,
      store: ProfileStore(database, 'profile-one'),
      profileId: 'profile-one',
    );
    final first = SpaceActorIdentity(id: 'space-a', slug: 'espace-a');
    final other = SpaceActorIdentity(id: 'space-b', slug: 'espace-b');
    final personal = repo.sourceFor('journey-1');
    final collective = repo.sourceFor('journey-1', space: first);
    final unrelated = repo.sourceFor('journey-1', space: other);

    expect(personal.actorScope.isPersonal, isTrue);
    expect(collective.actorScope.isSpace, isTrue);
    expect(collective.actorScope.spaceId, first.id);
    expect(personal.resourceKey, isNot(collective.resourceKey));
    expect(collective.resourceKey, isNot(unrelated.resourceKey));
    expect(collective.path, contains('/workspaces/espace-a/beneficiary/'));
  });

  test('retained Space owner data is scoped to Profile and Space', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final p1 = ProfileStore(database, 'profile-one');
    final p2 = ProfileStore(database, 'profile-two');
    final first = SpaceActorIdentity(id: 'space-a', slug: 'espace-a');
    final second = SpaceActorIdentity(id: 'space-b', slug: 'espace-b');
    const journeyId = 'journey-1';
    await p1.putProjection(
      kind: SpaceBeneficiaryJourneyRepository.projectionKind,
      resourceKey:
          SpaceBeneficiaryJourneyRepository.resourceKey(first, journeyId),
      schemaVersion: 1,
      payload: const {
        'identity': {
          'id': journeyId,
          'kind': 'journey',
          'beneficiary': {'kind': 'space', 'id': 'space-a'},
        },
        'service_request': {'objective': 'Préparer la demande collective'},
      },
    );
    expect(
      await p1.readProjection(
        SpaceBeneficiaryJourneyRepository.projectionKind,
        resourceKey:
            SpaceBeneficiaryJourneyRepository.resourceKey(first, journeyId),
      ),
      isNotNull,
    );
    expect(
      await p1.readProjection(
        SpaceBeneficiaryJourneyRepository.projectionKind,
        resourceKey:
            SpaceBeneficiaryJourneyRepository.resourceKey(second, journeyId),
      ),
      isNull,
    );
    expect(
      await p2.readProjection(
        SpaceBeneficiaryJourneyRepository.projectionKind,
        resourceKey:
            SpaceBeneficiaryJourneyRepository.resourceKey(first, journeyId),
      ),
      isNull,
    );
  });

  test('Space continuation source is explicitly actor-scoped', () {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-one');
    final repository = SpaceBeneficiaryJourneyListRepository(
      database: database,
      store: store,
      profileId: 'profile-one',
    );
    final space = SpaceActorIdentity(id: 'space-a', slug: 'espace-a');
    final source = repository.sourceFor(space);
    expect(source.actorScope.isSpace, isTrue);
    expect(source.actorScope.spaceId, space.id);
    expect(source.resourceKey, space.id);
    expect(source.path, contains('beneficiary/journeys/'));
  });
}
