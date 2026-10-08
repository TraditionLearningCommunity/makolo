import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/features/now/now_media_viewer.dart';
import 'package:makolo_mobile/platform/sharing/share_gateway.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

import 'fakes.dart';

class FakeNowMediaApi extends MakoloApiClient {
  FakeNowMediaApi()
    : super(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(),
      );

  String? downloadedPath;

  @override
  Future<ApiResponse> download(
    String path, {
    required String destinationPath,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) async {
    expect(path, 'api/v1/me/now/media/journey-artifacts/123/');
    downloadedPath = destinationPath;
    await File(destinationPath).writeAsBytes([1, 2, 3]);
    return const ApiResponse(200, '', {});
  }
}

class FakeNowMediaSharing implements ShareGateway {
  final shared = <String>[];

  @override
  Future<void> shareText(String text) async {}

  @override
  Future<void> shareFiles({required List<String> paths, String? text}) async {
    shared.addAll(paths);
  }

  @override
  Future<bool> openExternal(Uri uri) async => false;
}

void main() {
  testWidgets('in-app media requires an explicit native export action', (
    tester,
  ) async {
    final root = await Directory.systemTemp.createTemp('now-viewer-test-');
    final api = FakeNowMediaApi();
    final sharing = FakeNowMediaSharing();
    addTearDown(() async {
      api.close();
      if (await root.exists()) await root.delete(recursive: true);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: NowMediaViewer(
          api: api,
          sharing: sharing,
          temporaryDirectory: root,
          media: const NowMediaBindingPresentation(
            resourceRef: 'journey_artifact:123',
            target: NowMediaTarget.situation,
            purpose: NowMediaPurpose.prepare,
            kind: NowMediaKind.unknown,
            url: '/api/v1/me/now/media/journey-artifacts/123/',
            authorized: true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(api.downloadedPath, isNotNull);
    expect(sharing.shared, isEmpty);
    expect(find.byTooltip('Enregistrer sur l’appareil'), findsOneWidget);

    await tester.tap(find.byTooltip('Enregistrer sur l’appareil'));
    await tester.pump();
    expect(sharing.shared, [api.downloadedPath]);
  });
}
