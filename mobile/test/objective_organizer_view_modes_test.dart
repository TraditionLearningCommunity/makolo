import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/objective_organizer_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';

class _OwnerPreviewRepository extends Fake implements ObjectiveRepository {
  _OwnerPreviewRepository(this.snapshot);

  final StoredProjection snapshot;

  @override
  String get profileId => 'current';

  @override
  Stream<List<StoredProjection>> watchOrganizer() =>
      Stream.value([snapshot]);

  @override
  Stream<OwnerSourceState> watchOrganizerSource({String? spaceSlug}) =>
      Stream.value(OwnerSourceState.unknown);

  @override
  Future<StoredProjection?> readOrganizerPage(
    int offset, {
    String? spaceSlug,
  }) async => snapshot;

  @override
  Future<OwnerSourceState> readOrganizerSource({String? spaceSlug}) async =>
      OwnerSourceState.unknown;
}

void main() {
  testWidgets('three organizer modes differ and explorer uses genuine hierarchy', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(393, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final projection = StoredProjection(
      kind: 'objective.organizer.collection',
      schemaVersion: 1,
      receivedAt: DateTime.now().toUtc(),
      payload: {
        'actor': {'type': 'profile', 'id': 'current'},
        'actor_context': {'kind': 'personal'},
        'page': {
          'offset': 0,
          'limit': 50,
          'next_offset': 50,
          'has_more': false,
        },
        'items': [
          {
            'kind': 'project',
            'id': 'p',
            'title': 'Projet Voyage',
            'state': 'active',
            'relation': 'mine',
          },
          {
            'kind': 'dossier',
            'id': 'd',
            'title': 'Dossier Voyage',
            'state': 'active',
            'relation': 'mine',
            'project_id': 'p',
          },
          {
            'kind': 'journey',
            'id': 'j',
            'title': 'Acheter un billet',
            'state': 'active',
            'relation': 'mine',
            'dossier_ids': ['d'],
          },
          {
            'kind': 'journey',
            'id': 'independent',
            'title': 'Démarche indépendante',
            'state': 'active',
            'relation': 'mine',
            'dossier_ids': <String>[],
          },
        ],
      },
    );
    final opened = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        home: ObjectiveOrganizerScreen(
          repository: _OwnerPreviewRepository(projection),
          onOpenItem: (kind, id) => opened.add('$kind:$id'),
          onCreate: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Vue Liste'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('organizer-row-journey:j')), findsOneWidget);
    expect(find.byKey(const Key('organizer-open-journey:j')), findsNothing);

    await tester.tap(find.byTooltip('Vue Explorateur'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('organizer-row-journey:j')), findsNothing);
    expect(find.text('Par organisation'), findsOneWidget);
    expect(find.byKey(const Key('organizer-open-project:p')), findsOneWidget);
    expect(find.byKey(const Key('organizer-open-journey:j')), findsNothing);

    final root = find.byKey(const Key('organizer-open-project:p'));
    final independent = find.byKey(
      const Key('organizer-open-journey:independent'),
    );
    expect(independent, findsOneWidget);
    // No 28 px empty expander gutter on standalone root journeys.
    expect(
      tester.getTopLeft(independent).dx,
      lessThanOrEqualTo(tester.getTopLeft(root).dx + 4),
    );

    await tester.tap(find.byKey(const Key('organizer-expand-project:p')));
    await tester.pumpAndSettle();
    final dossier = find.byKey(const Key('organizer-open-dossier:d'));
    expect(dossier, findsOneWidget);
    expect(
      tester.getTopLeft(dossier).dx,
      greaterThan(tester.getTopLeft(root).dx),
    );
    await tester.tap(find.byKey(const Key('organizer-expand-dossier:d')));
    await tester.pumpAndSettle();
    final journey = find.byKey(const Key('organizer-open-journey:j'));
    expect(journey, findsOneWidget);
    expect(
      tester.getTopLeft(journey).dx,
      greaterThan(tester.getTopLeft(dossier).dx),
    );
    await tester.tap(journey);
    expect(opened.last, 'journey:j');
  });
}
