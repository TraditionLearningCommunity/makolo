import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/me/me_support_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Future<void> _mountAppuis(
  WidgetTester tester, {
  required int responseStatus,
  bool cached = false,
}) async {
  final database = MakoloDatabase.memory();
  addTearDown(database.close);
  final store = ProfileStore(database, 'profile-a');
  if (cached) {
    await store.putProjection(
      kind: 'appuis.loyalty',
      resourceKey: 'personal',
      schemaVersion: 1,
      payload: {
        'accounts': [
          {
            'id': 'account-one',
            'program': 'one',
            'program_name': 'Club connu',
            'points_balance': 0,
          },
        ],
        'memberships': <Object>[],
        'available_rewards': <Object>[],
        'rewards': <Object>[],
      },
    );
  }
  final tokens = MemoryTokenStore(
    session: const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    ),
  );
  final api = MakoloApiClient(
    baseUri: Uri.parse('https://makolo.invalid/'),
    tokenStore: tokens,
    dio: MockClient((request) async {
      return MockResponse('{"detail":"unavailable"}', responseStatus);
    }).dio,
  );
  addTearDown(api.close);
  final runtime = AppRuntime(
    tokens: tokens,
    session: const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    ),
    recovery: SessionRecoveryController(),
    store: store,
    database: database,
    api: api,
  );
  await tester.pumpWidget(MaterialApp(home: MeSupportScreen(runtime: runtime)));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Appuis keeps acquired content without three network warnings', (
    tester,
  ) async {
    await _mountAppuis(tester, responseStatus: 503, cached: true);
    expect(find.text('Club connu'), findsOneWidget);
    expect(find.textContaining('Actualisation impossible'), findsNothing);
    expect(find.textContaining('informations connues'), findsNothing);
    expect(find.textContaining('Données conservées'), findsNothing);
  });

  testWidgets('Appuis does not invent a confirmed empty state on outage', (
    tester,
  ) async {
    await _mountAppuis(tester, responseStatus: 503);
    expect(find.text('Appuis indisponibles.'), findsOneWidget);
    expect(find.textContaining('Aucun appui'), findsNothing);
    expect(find.textContaining('Actualisation impossible'), findsNothing);
  });

  testWidgets('Appuis reports revoked access once, not for each family', (
    tester,
  ) async {
    await _mountAppuis(tester, responseStatus: 403);
    expect(
      find.text('Certains appuis ne sont plus accessibles.'),
      findsOneWidget,
    );
    expect(find.textContaining('Actualisation impossible'), findsNothing);
  });
}
