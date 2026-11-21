import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/interoperability/intelligence_connection_controls.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets('N2/N3 use owner-provided names without overflow at 360dp', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 740));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final client = MockClient((request) async {
      expect(request.data, isNull);
      return MockResponse(
        jsonEncode({
          'offers': [
            {
              'code': 'dynamic-owner-example',
              'label': 'Service de recherche scientifique et documentaire',
              'description':
                  'Description assez longue pour vérifier '
                  'la composition à largeur réduite sans chevauchement.',
              'capabilities': ['web_research'],
              'requires_model': false,
              'can_connect': false,
            },
          ],
        }),
        200,
      );
    });
    const session = AuthSession(
      accessToken: 'token',
      refreshToken: 'refresh',
      profileId: 'layout-profile',
    );
    final tokens = MemoryTokenStore(session: session);
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      dio: client.dio,
      tokenStore: tokens,
    );
    addTearDown(api.close);
    final runtime = AppRuntime(
      tokens: tokens,
      session: session,
      recovery: SessionRecoveryController(),
      api: api,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(
            size: Size(360, 740),
            textScaler: TextScaler.linear(1.6),
          ),
          child: Scaffold(
            body: SingleChildScrollView(
              child: IntelligenceConnectionControls(
                runtime: runtime,
                path: 'api/v1/me/intelligence/connections/',
                connections: const [],
                onChanged: () async {},
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    expect(
      find.text('Service de recherche scientifique et documentaire'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
    await tester.tap(
      find.text('Service de recherche scientifique et documentaire'),
    );
    await tester.pump();
    expect(find.byKey(const Key('connection-n3')), findsOneWidget);
    expect(find.textContaining('Ce service reste consultable'), findsOneWidget);
    expect(find.byType(TextFormField), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
