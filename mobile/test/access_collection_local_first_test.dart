import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/access/access_collection_screen.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';

void main() {
  testWidgets('accesses distinguish missing cache from confirmed empty page', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'owner-a');
    final repository = AccessRepository(
      database: database,
      store: store,
      profileId: 'owner-a',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AccessCollectionScreen(
          repository: repository,
          onOpenAccess: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Vos accès ne sont pas encore disponibles sur cet appareil.'),
      findsOneWidget,
    );
    expect(find.text('Aucun accès disponible pour le moment.'), findsNothing);

    await store.putProjection(
      kind: AccessRepository.collectionProjectionKind,
      resourceKey: repository.collectionResourceKey(
        relationship: 'beneficiary',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: {
        'items': <Object>[],
        'page': {'offset': 0, 'limit': 24, 'has_more': false},
      },
    );
    await tester.pumpAndSettle();
    expect(find.text('Aucun accès disponible pour le moment.'), findsOneWidget);
  });
}
