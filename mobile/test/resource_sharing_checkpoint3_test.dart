import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/resources/resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/platform/sharing/share_gateway.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

class _ShareResourceRepository extends ResourceRepository {
  _ShareResourceRepository({
    required super.database,
    required super.store,
    required super.profileId,
  });

  String? exportedPath;
  bool? retainedOfflineCopy;
  String? requestedExtension;

  @override
  Future<ResourceSourceState> readDetailSource(String assetId) async =>
      ResourceSourceState(lastSuccessAt: DateTime.now().toUtc());

  @override
  Stream<ResourceSourceState> watchDetailSource(String assetId) =>
      Stream.value(
        ResourceSourceState(lastSuccessAt: DateTime.now().toUtc()),
      );

  @override
  Future<String> downloadVersionForExplicitExport({
    required String path,
    required String assetId,
    required String title,
    required int versionNumber,
    required bool retainOfflineCopy,
    String? fileExtension,
    TransferProgress? onProgress,
  }) async {
    this.retainedOfflineCopy = retainOfflineCopy;
    requestedExtension = fileExtension;
    final directory = await Directory.systemTemp.createTemp(
      'makolo-resource-share-',
    );
    final suffix = fileExtension == null || fileExtension.isEmpty
        ? ''
        : '.$fileExtension';
    final file = File(
      '${directory.path}/${title.replaceAll(' ', '-')}-v$versionNumber$suffix',
    );
    await file.writeAsString('private-owner-backed-content');
    exportedPath = file.path;
    onProgress?.call(28, 28);
    return file.path;
  }
}

class _RecordingShareGateway implements ShareGateway {
  final List<List<String>> sharedFiles = [];
  bool existedDuringShare = false;

  @override
  Future<void> shareText(String text) async {}

  @override
  Future<void> shareFiles({
    required List<String> paths,
    String? text,
  }) async {
    sharedFiles.add(List<String>.from(paths));
    existedDuringShare =
        paths.length == 1 && await File(paths.single).exists();
  }

  @override
  Future<bool> openExternal(Uri uri) async => true;
}

void main() {
  testWidgets(
    'Document share uses an explicit temporary owner export and cleans staging',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = _ShareResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      final sharing = _RecordingShareGateway();

      await store.putProjection(
        kind: ResourceRepository.detailProjectionKind,
        resourceKey: 'asset-share',
        schemaVersion: 1,
        payload: {
          'id': 'asset-share',
          'title': 'Pièce sensible',
          'asset_kind_label': 'Document d’identité',
          'sensitivity': 'sensitive',
          'sensitivity_label': 'Sensible',
          'status': 'active',
          'current_version': {
            'id': 'version-share',
            'version': 3,
            'current': true,
            'mime_type': 'application/pdf',
            'validity': {'state': 'current'},
            'provenance': {'kind': 'unknown'},
            'links': {
              'download':
                  '/api/v1/me/resources/versions/'
                  '00000000-0000-0000-0000-000000000003/download/',
            },
          },
          'versions': {
            'items': [
              {
                'id': 'version-share',
                'version': 3,
                'current': true,
                'mime_type': 'application/pdf',
                'validity': {'state': 'current'},
                'provenance': {'kind': 'unknown'},
                'links': {
                  'download':
                      '/api/v1/me/resources/versions/'
                      '00000000-0000-0000-0000-000000000003/download/',
                },
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
            assetId: 'asset-share',
            repository: repository,
            personal: PersonalRepository(store),
            sharing: sharing,
            onOpenJourney: (_) {},
            onAddVersion: () {},
            onArchived: () {},
          ),
        ),
      );
      await tester.pump();

      expect(find.byTooltip('Partager'), findsOneWidget);
      await tester.tap(find.byTooltip('Partager'));
      await tester.pumpAndSettle();

      expect(sharing.sharedFiles, hasLength(1));
      expect(sharing.existedDuringShare, isTrue);
      expect(repository.retainedOfflineCopy, isFalse);
      expect(repository.requestedExtension, 'pdf');
      expect(repository.exportedPath, isNotNull);
      expect(
        File(repository.exportedPath!).uri.pathSegments.last,
        'Pièce-sensible-v3.pdf',
      );
      expect(await File(repository.exportedPath!).exists(), isFalse);

      final parent = Directory(repository.exportedPath!).parent;
      if (await parent.exists()) await parent.delete(recursive: true);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
