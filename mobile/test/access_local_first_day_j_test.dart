import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/access/access_collection_screen.dart';
import 'package:makolo_mobile/features/access/access_detail_screen.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';

const _path = '/api/v1/me/accesses/access-1/credential/';

Map<String, dynamic> _knownAccess() => {
  'relationship': 'beneficiary',
  'items': [
    {
      'identity': {'kind': 'access', 'id': 'access-1'},
      'relationship': 'beneficiary',
      'activity': {'id': 'activity-1', 'title': 'Départ du 15 novembre'},
      'state': {'code': 'valid', 'label': 'Valide'},
      'occurrence': {
        'id': 'occurrence-1',
        'timing': {'start_at': '2026-11-15T07:30:00+02:00'},
        'place': {
          'name': 'Agence de départ',
          'locality': 'Lubumbashi',
          'address_line': 'Avenue du Départ',
          'access_instructions': 'Présentez-vous au guichet A.',
        },
      },
      'validity': {'until': '2026-11-15T10:00:00+02:00'},
      'capabilities': ['present_credential'],
      'links': {'credential': _path},
    },
  ],
  'page': {'offset': 0, 'limit': 24, 'has_more': false},
};

void main() {
  testWidgets(
    'day-J Access facts stay readable without a keyed detail or API',
    (tester) async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'profile-a');
      final repo = AccessRepository(
        database: db,
        store: store,
        profileId: 'profile-a',
      );
      await store.putProjection(
        kind: AccessRepository.collectionProjectionKind,
        resourceKey: repo.collectionResourceKey(
          relationship: 'beneficiary',
          offset: 0,
        ),
        schemaVersion: 1,
        payload: _knownAccess(),
      );
      String? openedCredential;
      await tester.pumpWidget(
        MaterialApp(
          home: AccessDetailScreen(
            accessId: 'access-1',
            repository: repo,
            onOpenDayOf: (_) {},
            onOpenCredential: (path) => openedCredential = path,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Départ du 15 novembre'), findsOneWidget);
      expect(find.text('Avenue du Départ'), findsOneWidget);
      expect(
        find.textContaining('Présentez-vous au guichet A.'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Ces informations ont été enregistrées'),
        findsOneWidget,
      );
      expect(
        find.textContaining('État lors de la dernière réception'),
        findsOneWidget,
      );
      expect(await repo.readKnownCredentialPath('access-1'), _path);
      await tester.tap(find.text('Préparer ou afficher mon QR'));
      await tester.pump();
      expect(openedCredential, _path);
      final other = AccessRepository(
        database: db,
        store: ProfileStore(db, 'profile-b'),
        profileId: 'profile-b',
      );
      expect(await other.readKnownCredentialPath('access-1'), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 1));
    },
  );

  testWidgets('explicit owner collection revocation hides Access facts', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-a');
    final repo = AccessRepository(
      database: db,
      store: store,
      profileId: 'profile-a',
    );
    await store.putProjection(
      kind: AccessRepository.collectionProjectionKind,
      resourceKey: repo.collectionResourceKey(
        relationship: 'beneficiary',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: _knownAccess(),
    );
    await db
        .into(db.syncSources)
        .insert(
          SyncSourcesCompanion.insert(
            profileId: 'profile-a',
            sourceKey: repo.collectionSourceKey(
              relationship: 'beneficiary',
              offset: 0,
            ),
            route: 'api/v1/me/accesses/',
            invalidated: const Value(true),
          ),
        );
    await tester.pumpWidget(
      MaterialApp(
        home: AccessCollectionScreen(repository: repo, onOpenAccess: (_) {}),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Départ du 15 novembre'), findsNothing);
    expect(find.textContaining('autorité actuelle'), findsOneWidget);
    expect(await repo.readKnownCredentialPath('access-1'), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
  });
}
