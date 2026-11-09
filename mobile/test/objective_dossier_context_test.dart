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
