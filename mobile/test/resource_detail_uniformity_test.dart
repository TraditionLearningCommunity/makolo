import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/resources/resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/resource_file_viewer.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

class _ReaderRepository extends ResourceRepository {
  _ReaderRepository({
    required super.database,
    required super.store,
    required super.profileId,
  });

  @override
  Future<bool> shouldRefreshDetail(String assetId, {DateTime? now}) async =>
      false;

  @override
  Future<ResourceSourceState> readDetailSource(String assetId) async =>
      ResourceSourceState(lastSuccessAt: DateTime.now().toUtc());

  @override
  Stream<ResourceSourceState> watchDetailSource(String assetId) =>
      Stream.value(ResourceSourceState(lastSuccessAt: DateTime.now().toUtc()));

  @override
  Future<String> downloadVersionForReader({
    required String path,
    required String assetId,
    required String title,
    required int versionNumber,
    required String extension,
    required bool textPreview,
    TransferProgress? onProgress,
  }) async {
    final directory = await Directory.systemTemp.createTemp(
      'makolo-resource-reader-test-',
    );
    final file = File('${directory.path}/Document-v$versionNumber.txt');
    await file.writeAsString('Lecture DOCX Makolo');
    onProgress?.call(18, 18);
    return file.path;
  }
}

void main() {
  testWidgets(
    'Document detail uses Passport-like actions and opens the main file inside Makolo',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = _ReaderRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );

      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-reader',
        schemaVersion: 1,
        payload: {
          'id': 'asset-reader',
          'title': 'Compte rendu',
          'asset_kind_label': 'Autre',
          'sensitivity': 'normal',
          'sensitivity_label': 'Normale',
          'status': 'active',
          'current_version': {
            'id': 'version-reader',
            'version': 1,
            'current': true,
            'mime_type':
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document',
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
                'id': 'version-reader',
                'version': 1,
                'current': true,
                'mime_type':
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document',
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
            'reuse_in_journey':
                '/api/v1/me/resources/versions/'
                '00000000-0000-0000-0000-000000000001/reuse/',
            'add_version':
                '/api/v1/me/resources/'
                '00000000-0000-0000-0000-000000000002/versions/',
            'archive':
                '/api/v1/me/resources/'
                '00000000-0000-0000-0000-000000000002/archive/',
          },
        },
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ResourceDetailScreen(
            assetId: 'asset-reader',
            repository: repository,
            personal: PersonalRepository(store),
            onOpenJourney: (_) {},
            onAddVersion: () {},
            onArchived: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byTooltip('Versions'), findsOneWidget);
      expect(find.byTooltip('Télécharger'), findsOneWidget);
      expect(find.byTooltip('Partager'), findsOneWidget);
      expect(find.byTooltip('Plus'), findsOneWidget);
      expect(find.byTooltip('Utiliser'), findsNothing);
      expect(find.byTooltip('Archiver'), findsNothing);
      expect(find.byTooltip('Nouvelle version'), findsOneWidget);
      expect(find.text('Normale'), findsNothing);

      await tester.tap(find.text('Version 1'));
      await tester.pumpAndSettle();

      expect(find.byType(ResourceFileViewer), findsOneWidget);
      expect(find.text('Lecture DOCX Makolo'), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Compte rendu'), findsOneWidget);
    },
  );
}
