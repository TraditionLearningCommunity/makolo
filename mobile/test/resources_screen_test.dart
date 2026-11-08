import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/resources/document_form_screen.dart';
import 'package:makolo_mobile/features/resources/documents_screen.dart';
import 'package:makolo_mobile/features/resources/resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/features/resources/resources_screen.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

void main() {
  testWidgets('Mes ressources is a compact three-family hub', (tester) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = ResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    await store.putProjection(
      kind: ResourceRepository.collectionProjectionKind,
      resourceKey: repository.collectionResourceKey(query: '', offset: 0),
      schemaVersion: 1,
      payload: {
        'documents': {
          'count': 4,
          'query': null,
          'view': 'current',
          'sort': 'recent',
          'filters': {'kind': null, 'sensitivity': null},
          'items': const [],
          'page': {'offset': 0, 'limit': 24, 'has_more': false},
        },
        'proofs': {'count': 2, 'items': const []},
        'credentials': {'count': 1, 'items': const []},
      },
    );

    var openedDocuments = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ResourcesScreen(
          repository: repository,
          onOpenDocuments: () => openedDocuments = true,
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Mes documents'), findsOneWidget);
    expect(find.text('Mes preuves'), findsOneWidget);
    expect(find.text('Mes titres'), findsOneWidget);
    expect(find.text('Bibliothèque'), findsNothing);
    expect(find.text('4'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    expect(find.text('1'), findsOneWidget);

    await tester.tap(find.text('Mes documents'));
    expect(openedDocuments, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Mes documents keeps search views filter and sort compact', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = ResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    await store.putProjection(
      kind: ResourceRepository.collectionProjectionKind,
      resourceKey: repository.collectionResourceKey(query: '', offset: 0),
      schemaVersion: 1,
      payload: {
        'documents': {
          'count': 2,
          'query': null,
          'view': 'current',
          'sort': 'recent',
          'filters': {'kind': null, 'sensitivity': null},
          'filter_options': {
            'kinds': [
              {'id': 'identity_document', 'label': 'Document d’identité'},
              {'id': 'form', 'label': 'Formulaire'},
            ],
            'sensitivities': [
              {'id': 'normal', 'label': 'Normale'},
              {'id': 'sensitive', 'label': 'Sensible'},
            ],
          },
          'items': [
            {
              'id': 'asset-1',
              'title': 'Passeport RDC',
              'asset_kind': 'identity_document',
              'asset_kind_label': 'Document d’identité',
              'sensitivity': 'normal',
              'sensitivity_label': 'Normale',
              'status': 'active',
              'current_version': {
                'version': 2,
                'validity': {
                  'state': 'current',
                  'expires_at': '2028-08-12',
                },
              },
            },
            {
              'id': 'asset-2',
              'title': 'Formulaire',
              'asset_kind': 'form',
              'asset_kind_label': 'Formulaire',
              'sensitivity': 'normal',
              'sensitivity_label': 'Normale',
              'status': 'active',
            },
          ],
          'page': {'count': 2, 'offset': 0, 'limit': 24, 'has_more': false},
        },
        'proofs': {'count': 0, 'items': const []},
        'credentials': {'count': 0, 'items': const []},
      },
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: DocumentsScreen(
          repository: repository,
          onOpenDocument: (_) {},
          onAddDocument: () {},
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Passeport RDC'), findsOneWidget);
    expect(find.text('Formulaire'), findsWidgets);
    expect(find.text('Tous'), findsOneWidget);
    expect(find.text('À échéance'), findsOneWidget);
    expect(find.text('Archivés'), findsOneWidget);
    expect(find.byTooltip('Filtrer'), findsOneWidget);
    expect(find.byTooltip('Trier'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Passeport');
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Passeport RDC'), findsOneWidget);
    expect(find.text('Formulaire'), findsNothing);

    await tester.enterText(find.byType(TextField), 'Inexistant');
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Passeport RDC'), findsNothing);
    expect(find.text('Aucun résultat'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Nouveau document stays a short professional form', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = ResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: DocumentFormScreen.create(
          repository: repository,
          onSaved: (_) {},
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Nouveau document'), findsOneWidget);
    expect(find.text('Titre'), findsOneWidget);
    expect(find.text('Type'), findsOneWidget);
    expect(find.text('Confidentialité'), findsOneWidget);
    expect(find.text('Choisir un fichier'), findsOneWidget);
    expect(find.byTooltip('Enregistrer'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'a document already visible keeps its safe summary offline',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      await store.putProjection(
        kind: ResourceRepository.collectionProjectionKind,
        resourceKey: repository.collectionResourceKey(query: '', offset: 0),
        schemaVersion: 1,
        payload: {
          'documents': {
            'query': null,
            'view': 'current',
            'sort': 'recent',
            'filters': {'kind': null, 'sensitivity': null},
            'items': [
              {
                'id': 'asset-seen',
                'title': 'Document déjà connu',
                'asset_kind_label': 'Attestation',
                'sensitivity': 'sensitive',
                'sensitivity_label': 'Sensible',
                'status': 'active',
              },
            ],
            'page': {'offset': 0, 'limit': 24, 'has_more': false},
          },
        },
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourceDetailScreen(
            assetId: 'asset-seen',
            repository: repository,
            personal: PersonalRepository(store),
            onOpenJourney: (_) {},
            onAddVersion: () {},
            onArchived: () {},
          ),
        ),
      );
      await tester.pump();

      expect(find.text('Document déjà connu'), findsOneWidget);
      expect(find.textContaining('Attestation · Sensible'), findsOneWidget);
      expect(find.byTooltip('Télécharger'), findsNothing);
      expect(find.byTooltip('Nouvelle version'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets(
    'PersonalAsset detail keeps provenance honest and copy concise',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-1',
        schemaVersion: 1,
        payload: {
          'id': 'asset-1',
          'title': 'Passeport RDC',
          'asset_kind_label': 'Document d’identité',
          'sensitivity': 'normal',
          'sensitivity_label': 'Normale',
          'status': 'active',
          'current_version': {
            'id': 'version-2',
            'version': 2,
            'current': true,
            'mime_type': 'application/pdf',
            'validity': {'state': 'current'},
            'provenance': {'kind': 'unknown'},
            'links': {},
          },
          'versions': {
            'items': [
              {
                'id': 'version-2',
                'version': 2,
                'current': true,
                'mime_type': 'application/pdf',
                'validity': {'state': 'current'},
                'provenance': {'kind': 'unknown'},
                'links': {},
              },
            ],
          },
          'links': {},
        },
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourceDetailScreen(
            assetId: 'asset-1',
            repository: repository,
            personal: PersonalRepository(store),
            onOpenJourney: (_) {},
            onAddVersion: () {},
            onArchived: () {},
          ),
        ),
      );
      await tester.pump();

      expect(find.text('Passeport RDC'), findsOneWidget);
      expect(find.textContaining('Provenance : Inconnue'), findsOneWidget);
      expect(
        find.textContaining('Conserver un document ne suffit pas'),
        findsNothing,
      );
      expect(find.textContaining('Requirement'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 1));
    },
  );
}
