import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/interoperability/push_device_controls.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  test('FCM registration, inventory and Z16 have distinct confirmations', () {
    expect(
      pushActivationConfirmation(
        devicesRefreshed: false,
        projectionRefreshed: false,
      ),
      contains('liste des appareils n’a pas pu être actualisée'),
    );
    expect(
      pushActivationConfirmation(
        devicesRefreshed: true,
        projectionRefreshed: false,
      ),
      contains('Actualisation encore nécessaire'),
    );
    expect(
      pushActivationConfirmation(
        devicesRefreshed: true,
        projectionRefreshed: true,
      ),
      contains('Notifications activées sur cet appareil'),
    );
  });

  testWidgets('owned push device can be revoked only through owner DELETE', (
    tester,
  ) async {
    var revoked = false;
    var mutations = 0;
    final requests = <String>[];
    final client = MockClient((request) async {
      requests.add(request.url.path);
      if (request.url.path.endsWith('/device-1/')) {
        expect(request.data, isNull);
        mutations++;
        revoked = true;
        return const MockResponse('', 204);
      }
      return MockResponse(
        jsonEncode({
          'results': revoked
              ? []
              : [
                  {
                    'id': 'device-1',
                    'provider': 'fcm',
                    'platform': 'android',
                    'device_name': 'Samsung Galaxy A54',
                    'active': true,
                    'app_version': '1.4',
                    'token_hint': 'NEVER-RENDER-HINT',
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
    var refreshed = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PushDeviceControls(
            runtime: runtime,
            mutationsEnabled: true,
            onChanged: () async => refreshed = true,
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Samsung Galaxy A54'), findsOneWidget);
    expect(find.textContaining('NEVER-RENDER-HINT'), findsNothing);
    await tester.tap(find.text('Retirer'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(mutations, 1);
    expect(refreshed, isTrue);
    expect(find.text('Aucun appareil enregistré.'), findsOneWidget);
    expect(
      requests,
      contains('/api/v1/notifications/push/endpoints/device-1/'),
    );
  });

  testWidgets('stale projection has read-only device actions', (tester) async {
    var mutations = 0;
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/device-2/')) {
        mutations++;
        return const MockResponse('', 204);
      }
      return const MockResponse(
        '{"results":[{"id":"device-2","provider":"fcm",'
        '"platform":"ios","active":true,"app_version":""}]}',
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
          body: PushDeviceControls(
            runtime: runtime,
            mutationsEnabled: false,
            onChanged: () async {},
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    final button = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Retirer'),
    );
    expect(button.onPressed, isNull);
    expect(mutations, 0);
  });
}
