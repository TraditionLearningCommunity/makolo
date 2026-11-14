import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/resources/documents_screen.dart';
import 'package:makolo_mobile/features/resources/resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/features/resources/resources_screen.dart';
import 'package:makolo_mobile/features/resources/trust_resource_collection_screen.dart';
import 'package:makolo_mobile/features/resources/trust_resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/trust_resource_repository.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

Future<void> _sourceState(
  MakoloDatabase database, {
  required String sourceKey,
  required String route,
  DateTime? lastSuccessAt,
  String? error,
  bool invalidated = false,
}) async {
  await database
      .into(database.syncSources)
      .insert(
        SyncSourcesCompanion.insert(
          profileId: 'profile-a',
          sourceKey: sourceKey,
          route: route,
          lastSuccessAt: Value(lastSuccessAt),
          invalidated: Value(invalidated),
          lastErrorCode: Value(error),
        ),
      );
}

Map<String, dynamic> _documentCollection(String id) => {
  'documents': {
    'query': '',
    'view': 'current',
    'sort': 'recent',
    'filters': {'kind': '', 'sensitivity': ''},
    'count': 1,
    'filter_options': {'kinds': <Object>[], 'sensitivities': <Object>[]},
    'items': [
      {
        'id': id,
        'title': 'Document connu',
        'asset_kind': 'other',
        'asset_kind_label': 'Document',
        'sensitivity': 'normal',
        'status': 'active',
      },
    ],
    'page': {'offset': 0, 'limit': 24, 'count': 1, 'has_more': false},
  },
  'proofs': {'count': 0, 'items': <Object>[]},
  'credentials': {'count': 0, 'items': <Object>[]},
};

void main() {
  testWidgets(
    'resource hub keeps navigation and unknown counts when aggregate refresh fails',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.collectionSourceFor(query: '', offset: 0);
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        error: 'transport_error',
      );

      var openedDocuments = false;
      var openedProofs = false;
      var openedTitles = false;
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourcesScreen(
            repository: repository,
            onOpenDocuments: () => openedDocuments = true,
            onOpenProofs: () => openedProofs = true,
            onOpenTitles: () => openedTitles = true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Les compteurs ne peuvent pas être actualisés pour le moment.',
        ),
        findsOneWidget,
      );
      expect(find.text('Mes documents'), findsOneWidget);
      expect(find.text('Mes preuves'), findsOneWidget);
      expect(find.text('Mes titres'), findsOneWidget);
      expect(find.text('0'), findsNothing);

      await tester.tap(find.text('Mes documents'));
      await tester.tap(find.text('Mes preuves'));
      await tester.tap(find.text('Mes titres'));
      expect(openedDocuments, isTrue);
      expect(openedProofs, isTrue);
      expect(openedTitles, isTrue);
    },
  );

  testWidgets(
    'documents never turn a failed first acquisition into an empty state',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.collectionSourceFor(query: '', offset: 0);
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        error: 'transport_error',
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
      await tester.pumpAndSettle();

      expect(
        find.text('Impossible d’actualiser vos documents.'),
        findsOneWidget,
      );
      expect(find.text('Aucun document'), findsNothing);
      expect(find.text('Réessayer'), findsOneWidget);
    },
  );

  testWidgets(
    'documents keep acquired content without passive network narration at 1.6x',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(430, 932);
      addTearDown(() {
        tester.view.resetDevicePixelRatio();
        tester.view.resetPhysicalSize();
      });

      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.collectionSourceFor(query: '', offset: 0);
      await store.putProjection(
        kind: ResourceRepository.collectionProjectionKind,
        resourceKey: source.resourceKey,
        schemaVersion: 1,
        payload: _documentCollection('asset-1'),
      );
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        lastSuccessAt: DateTime.now().toUtc().subtract(
          const Duration(minutes: 5),
        ),
        error: 'transport_error',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
            child: DocumentsScreen(
              repository: repository,
              onOpenDocument: (_) {},
              onAddDocument: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Document connu'), findsOneWidget);
      expect(
        find.text(
          'Données enregistrées sur cet appareil. Mise à jour indisponible.',
        ),
        findsNothing,
      );
      expect(find.text('Aucun document'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'normal document without a retained copy does not attempt an offline network download',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.detailSourceFor('asset-normal-offline');
      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-normal-offline',
        schemaVersion: 1,
        payload: {
          'id': 'asset-normal-offline',
          'title': 'Document normal',
          'asset_kind_label': 'Document',
          'sensitivity': 'normal',
          'sensitivity_label': 'Normale',
          'status': 'active',
          'current_version': {
            'id': 'version-normal',
            'version': 1,
            'current': true,
            'mime_type': 'application/pdf',
            'validity': {'state': 'current'},
            'provenance': {'kind': 'unknown'},
            'links': {
              'download':
                  '/api/v1/me/resources/versions/'
                  '00000000-0000-0000-0000-000000000010/download/',
            },
          },
          'versions': {
            'items': [
              {
                'id': 'version-normal',
                'version': 1,
                'current': true,
                'mime_type': 'application/pdf',
                'validity': {'state': 'current'},
                'provenance': {'kind': 'unknown'},
                'links': {
                  'download':
                      '/api/v1/me/resources/versions/'
                      '00000000-0000-0000-0000-000000000010/download/',
                },
              },
            ],
          },
          'links': {},
        },
      );
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        lastSuccessAt: DateTime.now().toUtc().subtract(
          const Duration(minutes: 5),
        ),
        error: 'transport_error',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourceDetailScreen(
            assetId: 'asset-normal-offline',
            repository: repository,
            personal: PersonalRepository(store),
            onOpenJourney: (_) {},
            onAddVersion: () {},
            onArchived: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Télécharger').first);
      await tester.pump();

      expect(
        find.text('Ce fichier n’est pas disponible hors connexion.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'sensitive document stays understandable offline without an active share action',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = ResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.detailSourceFor('asset-sensitive');
      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-sensitive',
        schemaVersion: 1,
        payload: {
          'id': 'asset-sensitive',
          'title': 'Pièce sensible',
          'asset_kind_label': 'Identité',
          'sensitivity': 'sensitive',
          'sensitivity_label': 'Sensible',
          'status': 'active',
          'current_version': {
            'id': 'version-1',
            'version': 1,
            'current': true,
            'mime_type': 'application/pdf',
            'validity': {'state': 'current'},
            'provenance': {'kind': 'unknown'},
            'links': {
              'download':
                  '/api/v1/me/resources/versions/'
                  '00000000-0000-0000-0000-000000000001/download/',
            },
          },
          'versions': {
            'items': [
              {
                'id': 'version-1',
                'version': 1,
                'current': true,
                'mime_type': 'application/pdf',
                'validity': {'state': 'current'},
                'provenance': {'kind': 'unknown'},
                'links': {
                  'download':
                      '/api/v1/me/resources/versions/'
                      '00000000-0000-0000-0000-000000000001/download/',
                },
              },
            ],
          },
          'links': {
            'reuse':
                '/api/v1/me/resources/versions/'
                '00000000-0000-0000-0000-000000000001/reuse/',
          },
        },
      );
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        lastSuccessAt: DateTime.now().toUtc().subtract(
          const Duration(minutes: 5),
        ),
        error: 'transport_error',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourceDetailScreen(
            assetId: 'asset-sensitive',
            repository: repository,
            personal: PersonalRepository(store),
            onOpenJourney: (_) {},
            onAddVersion: () {},
            onArchived: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Pièce sensible'), findsOneWidget);
      expect(
        find.text('Fichier disponible lorsque vous êtes connecté.'),
        findsOneWidget,
      );
      final share = tester.widget<IconButton>(
        find.descendant(
          of: find.byTooltip('Partager'),
          matching: find.byType(IconButton),
        ),
      );
      expect(share.onPressed, isNull);
    },
  );

  testWidgets(
    'Trust collection failure is unavailable rather than a false empty',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = TrustResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.collectionSourceFor(
        family: TrustResourceFamily.proofs,
        query: '',
        offset: 0,
      );
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        error: 'transport_error',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: TrustResourceCollectionScreen(
            family: TrustResourceFamily.proofs,
            repository: repository,
            onOpenItem: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Impossible d’actualiser vos preuves.'), findsOneWidget);
      expect(find.text('Aucune preuve'), findsNothing);
    },
  );

  testWidgets(
    'revoked Trust detail hides verification and sharing capabilities',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = TrustResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final source = repository.detailSourceFor(
        TrustResourceFamily.proofs,
        'proof-denied',
      );
      await store.putProjection(
        kind: TrustResourceFamily.proofs.detailProjection,
        resourceKey: 'proof-denied',
        schemaVersion: 1,
        payload: {
          'id': 'proof-denied',
          'proof_type_label': 'Journey accomplie',
          'status_label': 'Active',
          'issued_at': '2026-11-01T10:00:00Z',
          'links': {
            'verify': '/trust/proofs/verify/public-proof/',
            'passport': '/api/v1/me/passport/',
          },
        },
      );
      await _sourceState(
        database,
        sourceKey: source.sourceKey,
        route: source.path,
        invalidated: true,
        error: 'permission_denied',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: TrustResourceDetailScreen(
            family: TrustResourceFamily.proofs,
            id: 'proof-denied',
            repository: repository,
            onOpenJourney: (_) {},
            onOpenPassport: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Preuve indisponible'), findsOneWidget);
      expect(find.byTooltip('Vérifier'), findsNothing);
      expect(find.byTooltip('Partager'), findsNothing);
      expect(find.text('Passeport'), findsNothing);
    },
  );
}
