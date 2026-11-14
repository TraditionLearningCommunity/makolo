import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/interoperability/connections_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/interoperability_repository.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets('server commit with failed Z16 refresh is never optimistic', (
    tester,
  ) async {
    var z16Reads = 0;
    var posted = false;
    const privateKey = 'C8-PRIVATE-TEMPORARY-KEY';
    final client = MockClient((request) async {
      if (request.url.path == '/api/v1/me/interoperability/') {
        z16Reads++;
        if (z16Reads > 1) throw const SocketException('offline');
        return const MockResponse(
          '{"schema_version":"z16.v1","context":"profile",'
          '"providers":[],"connections":[],"actions":[],'
          '"extensions":[],"domain_integrations":[],"webhooks":[]}',
          200,
        );
      }
      if (request.url.path == '/api/v1/me/intelligence/connections/') {
        if (request.data != null) {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['api_key'], privateKey);
          expect(body['consent'], true);
          posted = true;
          return const MockResponse('{"id":"connection-confirmed"}', 201);
        }
        return const MockResponse(
          '{"offers":[{"code":"tavily","label":"Tavily",'
          '"description":"Recherche avec clé personnelle",'
          '"requires_model":false,"can_connect":true,'
          '"capabilities":["web_research"]}]}',
          200,
        );
      }
      throw StateError('Unexpected owner request: ${request.url.path}');
    });
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final session = const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'c8-profile',
    );
    final tokens = MemoryTokenStore(session: session);
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      dio: client.dio,
      tokenStore: tokens,
    );
    addTearDown(api.close);
    final store = ProfileStore(database, 'c8-profile');
    final runtime = AppRuntime(
      tokens: tokens,
      session: session,
      api: api,
      recovery: SessionRecoveryController(),
      database: database,
      store: store,
      interoperability: ProfileInteroperabilityRepository(store),
      sync: SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'c8-profile',
      ),
    );
    await tester.pumpWidget(
      MaterialApp(home: ProfileConnectionsScreen(runtime: runtime)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Tavily'), findsOneWidget);
    await tester.ensureVisible(find.text('Tavily'));
    await tester.tap(find.text('Tavily'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.enterText(find.byType(TextField).last, privateKey);
    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Connecter'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(posted, isTrue);
    expect(z16Reads, greaterThanOrEqualTo(2));
    expect(
      find.textContaining('Modification enregistrée sur le serveur, mais'),
      findsOneWidget,
    );
    final stored = await store.readProjection(
      ProfileInteroperabilityRepository.projectionKind,
    );
    expect(stored, isNotNull);
    expect(stored!.payload['connections'], isEmpty);
    expect(jsonEncode(stored.payload), isNot(contains(privateKey)));
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 500));
  });
}
