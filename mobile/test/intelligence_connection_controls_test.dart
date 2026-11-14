import 'dart:convert';

import 'dio_testing.dart';
import 'fakes.dart';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/interoperability/intelligence_connection_controls.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

void main() {
  testWidgets(
    'a real provider key goes only to the owner POST, never into a projection',
    (tester) async {
      final sent = <String>[];
      final client = MockClient((request) async {
        if (request.data == null) {
          expect(request.url.path, '/api/v1/me/intelligence/connections/');
          return MockResponse(
            jsonEncode({
              'offers': [
                {
                  'code': 'tavily',
                  'label': 'Tavily',
                  'description': 'Recherche Web avec votre clé.',
                  'capabilities': ['web_research'],
                  'requires_model': false,
                  'can_connect': true,
                },
              ],
            }),
            200,
          );
        }
        expect(request.url.path, '/api/v1/me/intelligence/connections/');
        final requestBody = jsonDecode(request.body);
        expect(requestBody['provider'], 'tavily');
        expect(requestBody['consent'], isTrue);
        sent.add(requestBody['api_key'] as String);
        return MockResponse('{"id":"new-connection","scope":"profile"}', 201);
      });
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'token',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: client.dio,
        tokenStore: tokens,
      );
      addTearDown(api.close);
      final runtime = AppRuntime(
        tokens: tokens,
        session: const AuthSession(
          accessToken: 'token',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        api: api,
      );
      var refreshed = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: IntelligenceConnectionControls(
              runtime: runtime,
              path: 'api/v1/me/intelligence/connections/',
              connections: const [],
              onChanged: () async {
                refreshed = true;
              },
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.text('Tavily'), findsOneWidget);
      await tester.tap(find.text('Tavily'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      final fields = find.byType(TextField);
      expect(fields, findsNWidgets(2));
      await tester.enterText(fields.at(0), 'Ma recherche');
      await tester.enterText(fields.at(1), 'SENSITIVE-DO-NOT-RENDER');
      expect(find.text('SENSITIVE-DO-NOT-RENDER'), findsNothing);
      await tester.ensureVisible(find.byType(Checkbox));
      await tester.tap(find.byType(Checkbox));
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Connecter'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(sent, ['SENSITIVE-DO-NOT-RENDER']);
      expect(refreshed, isTrue);
      expect(find.text('SENSITIVE-DO-NOT-RENDER'), findsNothing);
    },
  );
  testWidgets(
    'stale or offline connection controls cannot start a key upload',
    (tester) async {
      final client = MockClient((request) async {
        expect(request.data, isNull, reason: 'Mutations must remain disabled');
        return MockResponse(
          jsonEncode({
            'offers': [
              {
                'code': 'tavily',
                'label': 'Tavily',
                'description': 'Recherche Web avec votre clé.',
                'capabilities': ['web_research'],
                'requires_model': false,
                'can_connect': true,
              },
            ],
          }),
          200,
        );
      });
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'token',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: client.dio,
        tokenStore: tokens,
      );
      addTearDown(api.close);
      final runtime = AppRuntime(
        tokens: tokens,
        session: const AuthSession(
          accessToken: 'token',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        api: api,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: IntelligenceConnectionControls(
              runtime: runtime,
              path: 'api/v1/me/intelligence/connections/',
              connections: const [],
              mutationsEnabled: false,
              onChanged: () async {},
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 150));
      final offerTile = tester.widget<ListTile>(
        find.ancestor(of: find.text('Tavily'), matching: find.byType(ListTile)),
      );
      expect(
        offerTile.onTap,
        isNotNull,
        reason: 'Discovery stays readable without mutation rights',
      );
      await tester.tap(find.text('Tavily'));
      await tester.pump();
      expect(find.byType(TextFormField), findsNothing);
      expect(
        find.textContaining('Ce service reste consultable'),
        findsOneWidget,
      );
    },
  );
}
