import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/features/now/now_media_viewer.dart';
import 'package:makolo_mobile/features/now/now_inline_media_preview.dart';
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
    expect(
      path,
      'api/v1/me/now/media/journey-artifacts/11111111-2222-4333-8444-555555555555/',
    );
    downloadedPath = destinationPath;
    File(destinationPath).writeAsBytesSync([1, 2, 3]);
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
  testWidgets('unauthorized photo preview makes no authenticated request', (
    tester,
  ) async {
    late final Directory root;
    await tester.runAsync(() async {
      root = await Directory.systemTemp.createTemp('now-preview-test-');
    });
    final api = FakeNowMediaApi();
    addTearDown(() async {
      api.close();
      if (await root.exists()) await root.delete(recursive: true);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            height: 240,
            child: NowInlineMediaPreview(
              api: api,
              profileId: 'profile-a',
              temporaryDirectory: root,
              placeholder: const Text('Accès non disponible'),
              media: const NowMediaBindingPresentation(
                resourceRef:
                    'journey_artifact:11111111-2222-4333-8444-555555555555',
                target: NowMediaTarget.situation,
                purpose: NowMediaPurpose.understand,
                kind: NowMediaKind.image,
                authorized: false,
                url: '/api/v1/me/now/media/journey-artifacts/11111111-2222-4333-8444-555555555555/',
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(api.downloadedPath, isNull);
    expect(find.text('Accès non disponible'), findsOneWidget);
  });

  testWidgets('in-app media requires an explicit native export action', (
    tester,
  ) async {
    late final Directory root;
    await tester.runAsync(() async {
      root = await Directory.systemTemp.createTemp('now-viewer-test-');
      await Directory('${root.path}/makolo-now-media').create();
    });
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
            resourceRef:
                'journey_artifact:11111111-2222-4333-8444-555555555555',
            target: NowMediaTarget.situation,
            purpose: NowMediaPurpose.prepare,
            kind: NowMediaKind.unknown,
            url: '/api/v1/me/now/media/journey-artifacts/11111111-2222-4333-8444-555555555555/',
            authorized: true,
          ),
        ),
      ),
    );
    await tester.pump();
    expect(api.downloadedPath, isNotNull);
    expect(sharing.shared, isEmpty);
    expect(find.byTooltip('Enregistrer sur l’appareil'), findsOneWidget);

    await tester.runAsync(() async {
      await tester.tap(find.byTooltip('Enregistrer sur l’appareil'));
      await tester.pump();
    });
    expect(sharing.shared, [api.downloadedPath]);
  });
}
