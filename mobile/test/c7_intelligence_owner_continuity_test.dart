import 'dart:async';
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

Map<String, Object?> offer(String code) => {
  'code': code,
  'label': code == 'tavily' ? 'Ancien propriétaire' : 'Nouveau propriétaire',
  'description': 'Fournisseur de test',
  'capabilities': ['web_research'],
  'requires_model': false,
  'can_connect': true,
};

void main() {
  testWidgets('catalog from previous owner cannot replace a newer catalog', (
    tester,
  ) async {
    final previous = Completer<MockResponse>();
    final sent = <String>[];
    final client = MockClient((request) async {
      sent.add(request.url.path);
      if (request.url.path == '/api/v1/me/intelligence/connections/') {
        return previous.future;
      }
      return MockResponse(
        jsonEncode({
          'offers': [offer('exa')],
        }),
        200,
      );
    });
    final session = const AuthSession(
      accessToken: 'token',
      refreshToken: 'refresh',
      profileId: 'p1',
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
    Widget screen(String path) => MaterialApp(
      home: Scaffold(
        body: IntelligenceConnectionControls(
          runtime: runtime,
          path: path,
          connections: const [],
          onChanged: () async {},
        ),
      ),
    );

    await tester.pumpWidget(screen('api/v1/me/intelligence/connections/'));
    await tester.pump();
    await tester.pumpWidget(
      screen('api/v1/organizations/workspaces/new/intelligence/connections/'),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Nouveau propriétaire'), findsOneWidget);
    previous.complete(
      MockResponse(
        jsonEncode({
          'offers': [offer('tavily')],
        }),
        200,
      ),
    );
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Ancien propriétaire'), findsNothing);
    expect(find.text('Nouveau propriétaire'), findsOneWidget);
    expect(sent, contains('/api/v1/me/intelligence/connections/'));
    expect(
      sent,
      contains(
        '/api/v1/organizations/workspaces/new/intelligence/connections/',
      ),
    );
  });

  testWidgets(
    'owner scope change while consent dialog is open never sends key',
    (tester) async {
      var posted = false;
      final client = MockClient((request) async {
        if (request.data != null) {
          posted = true;
          return const MockResponse('{}', 201);
        }
        return MockResponse(
          jsonEncode({
            'offers': [offer('tavily')],
          }),
          200,
        );
      });
      final session = const AuthSession(
        accessToken: 'token',
        refreshToken: 'refresh',
        profileId: 'p1',
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
      final currentPath = ValueNotifier<String>(
        'api/v1/me/intelligence/connections/',
      );
      addTearDown(currentPath.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: ValueListenableBuilder<String>(
            valueListenable: currentPath,
            builder: (context, path, _) => Scaffold(
              body: IntelligenceConnectionControls(
                runtime: runtime,
                path: path,
                connections: const [],
                onChanged: () async {},
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      await tester.tap(find.text('Ancien propriétaire'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Relier ce service'), findsOneWidget);
      currentPath.value =
          'api/v1/organizations/workspaces/new/intelligence/connections/';
      await tester.pump();
      final fields = find.byType(TextField);
      await tester.enterText(fields.at(1), 'SECRET-OLD-OWNER');
      await tester.ensureVisible(find.byType(Checkbox));
      await tester.tap(find.byType(Checkbox));
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Connecter'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(posted, false);
    },
  );
}
