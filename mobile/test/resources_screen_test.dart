import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/resources/resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/features/resources/resources_screen.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

void main() {
  testWidgets(
    'Mes ressources keeps documents Proofs and Credentials distinct',
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
            'items': [
              {
                'id': 'asset-1',
                'title': 'Passeport RDC',
                'asset_kind_label': 'Document d’identité',
                'sensitivity_label': 'Sensible',
                'current_version': {
                  'version': 2,
                  'validity': {'state': 'current'},
                },
              },
            ],
            'page': {'offset': 0, 'limit': 24, 'has_more': false},
          },
          'proofs': {
            'items': [
              {
                'id': 'proof-1',
                'proof_type_label': 'Participation',
                'status_label': 'Établie',
              },
            ],
          },
          'credentials': {
            'items': [
              {
                'id': 'credential-1',
                'title': 'Attestation de participation',
                'status_label': 'Valide',
              },
            ],
          },
        },
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourcesScreen(repository: repository, onOpenResource: (_) {}),
        ),
      );
      await tester.pump();

      expect(find.text('Bibliothèque'), findsOneWidget);
      expect(find.text('Proofs'), findsOneWidget);
      expect(find.text('Credentials'), findsOneWidget);
      expect(find.text('Passeport RDC'), findsOneWidget);
      expect(find.text('Participation'), findsOneWidget);
      expect(find.text('Attestation de participation'), findsOneWidget);
      expect(find.text('Rechercher dans mes documents'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );

  testWidgets(
    'PersonalAsset detail says unknown provenance and no fake Requirement success',
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
            'validity': {'state': 'current'},
            'provenance': {'kind': 'unknown'},
          },
          'versions': {
            'items': [
              {
                'id': 'version-2',
                'version': 2,
                'current': true,
                'validity': {'state': 'current'},
                'provenance': {'kind': 'unknown'},
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
          ),
        ),
      );
      await tester.pump();

      expect(find.text('Passeport RDC'), findsOneWidget);
      expect(find.textContaining('Provenance : inconnue'), findsOneWidget);
      expect(
        find.text('Présence dans la Bibliothèque ≠ exigence satisfaite.'),
        findsOneWidget,
      );
      expect(find.textContaining('Requirement satisfait'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );
}
