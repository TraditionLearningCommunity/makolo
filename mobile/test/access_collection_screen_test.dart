import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/access/access_collection_screen.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';

Map<String, dynamic> payload({
  required String relationship,
  String accessId = 'access-1',
  String title = 'Voyage Lubumbashi → Kolwezi',
  String? holder,
}) {
  return {
    'relationship': relationship,
    'items': [
      {
        'identity': {'kind': 'access', 'id': accessId},
        'relationship': relationship,
        'state': {'code': 'valid', 'label': 'Valide'},
        'activity': {'id': 'activity-1', 'title': title},
        'occurrence': {
          'id': 'occurrence-1',
          'timing': {'start_at': '2026-10-10T07:30:00+02:00'},
          'place': {'name': 'Gare centrale'},
        },
        'validity': {
          'from': '2026-10-10T05:30:00Z',
          'until': '2026-10-10T10:00:00Z',
        },
        'holder': holder == null
            ? null
            : {'kind': 'profile', 'display_name': holder},
        'credential': relationship == 'beneficiary'
            ? {'available': true, 'type': 'qr', 'presentable': true}
            : null,
        'capabilities': relationship == 'beneficiary'
            ? ['present_credential']
            : <String>[],
      },
    ],
    'page': {'count': 1, 'offset': 0, 'limit': 24, 'has_more': false},
  };
}

void main() {
  testWidgets('Mes accès renders the right without exposing credential bytes', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = AccessRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    await store.putProjection(
      kind: AccessRepository.collectionProjectionKind,
      resourceKey: repository.collectionResourceKey(
        relationship: 'beneficiary',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: payload(relationship: 'beneficiary'),
    );

    String? opened;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: AccessCollectionScreen(
          repository: repository,
          onOpenAccess: (id) => opened = id,
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Mes accès'), findsOneWidget);
    expect(find.text('Voyage Lubumbashi → Kolwezi'), findsOneWidget);
    expect(find.textContaining('Valide'), findsOneWidget);
    expect(find.textContaining('payload'), findsNothing);

    await tester.tap(find.text('Voyage Lubumbashi → Kolwezi'));
    await tester.pump();
    expect(opened, 'access-1');
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
  });

  testWidgets('purchased for other keeps the holder relationship explicit', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = AccessRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    await store.putProjection(
      kind: AccessRepository.collectionProjectionKind,
      resourceKey: repository.collectionResourceKey(
        relationship: 'purchased_for_other',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: payload(
        relationship: 'purchased_for_other',
        accessId: 'access-other',
        title: 'Programme Comptabilité',
        holder: 'Benoît Mulumba',
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: AccessCollectionScreen(
          repository: repository,
          onOpenAccess: (_) {},
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Pour une autre personne'));
    await tester.pump();

    expect(find.text('Programme Comptabilité'), findsOneWidget);
    expect(find.textContaining('Pour Benoît Mulumba'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
  });
}
