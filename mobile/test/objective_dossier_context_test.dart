import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';

void main() {
  test('Dossier identity is stable but Space local snapshots are isolated', () {
    expect(ObjectiveRepository.detailResourceKey('dossier-1'), 'dossier-1');
    expect(
      ObjectiveRepository.detailResourceKey('dossier-1', spaceSlug: 'space-a'),
      'dossier-1:space:space-a',
    );
    expect(
      ObjectiveRepository.detailResourceKey('dossier-1', spaceSlug: 'space-b'),
      isNot('dossier-1:space:space-a'),
    );
    expect(
      ObjectiveRepository.projectDossierStorageKey('project-1', 0),
      'project-1:0:50',
    );
    expect(
      ObjectiveRepository.projectDossierStorageKey(
        'project-1',
        0,
        spaceSlug: 'space-a',
      ),
      'project-1:space:space-a:0:50',
    );
    expect(
      ObjectiveRepository.projectDossierStorageKey(
        'project-1',
        0,
        spaceSlug: 'space-b',
      ),
      isNot('project-1:space:space-a:0:50'),
    );
    expect(ObjectiveRepository.organizerStorageKey(0), 'offset:0:limit:50');
    expect(
      ObjectiveRepository.organizerStorageKey(0, spaceSlug: 'space-a'),
      'space:space-a:offset:0:limit:50',
    );
    expect(
      ObjectiveRepository.organizerStorageKey(0, spaceSlug: 'space-b'),
      isNot('space:space-a:offset:0:limit:50'),
    );
    expect(ObjectiveRepository.contextQuery(null), isEmpty);
    expect(
      ObjectiveRepository.contextQuery('space-a'),
      '?context=space&space=space-a',
    );
    expect(
      ObjectiveRepository.contextQuery('espace test'),
      '?context=space&space=espace%20test',
    );
  });
}
