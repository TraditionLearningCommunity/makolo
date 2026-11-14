import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/interoperability/space_connections_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  _ActorStore(this.initial);

  final ActorContext initial;

  @override
  Future<ActorContext> readActorContext(String profileId) async => initial;

  @override
  Future<void> writeActorContext(
    String profileId,
    ActorContext context,
  ) async {}

  @override
  Future<void> removeActorContext(String profileId) async {}
}

void main() {
  testWidgets(
    'late response from Space A is dropped after actor selects Space B',
    (tester) async {
      final oldResult = Completer<MockResponse>();
      final client = MockClient((request) async {
        if (request.url.path.endsWith('/interoperability/')) {
          return oldResult.future;
        }
        return const MockResponse('{"offers":[]}', 200);
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
      final spaceA = SpaceActorIdentity(id: 'a', slug: 'alpha');
      final spaceB = SpaceActorIdentity(id: 'b', slug: 'beta');
      final actor = await ActorContextController.restore(
        profileId: 'p1',
        store: _ActorStore(SpaceActorContext(space: spaceA)),
      );
      addTearDown(actor.dispose);
      final runtime = AppRuntime(
        tokens: tokens,
        session: session,
        recovery: SessionRecoveryController(),
        actorContext: actor,
        api: api,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: SpaceConnectionsScreen(runtime: runtime, slug: 'alpha'),
        ),
      );
      await tester.pump();
      await actor.selectSpace(spaceB);
      await tester.pump();
      oldResult.complete(
        MockResponse(
          jsonEncode({
            'schema_version': 'z16.v1',
            'context': 'space',
            'connections': [
              {
                'id': 'secret-a',
                'scope': 'space',
                'owner': 'intelligence',
                'display_name': 'Service du premier espace',
                'provider_protocol': 'tavily_search',
                'enabled': true,
                'available': true,
                'connected': true,
                'usable': true,
                'manageable': true,
                'health': 'healthy',
                'status': 'connected',
                'capabilities': ['web_research'],
              },
            ],
            'domain_integrations': [],
          }),
          200,
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Service du premier espace'), findsNothing);
      expect(find.text('Choisissez un Espace autorisé.'), findsOneWidget);
    },
  );

  testWidgets('Space projection observed while sync is offline is read-only', (
    tester,
  ) async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/interoperability/')) {
        return const MockResponse(
          '{"schema_version":"z16.v1","context":"space",'
          '"connections":[],"domain_integrations":[]}',
          200,
        );
      }
      if (request.url.path.endsWith('/intelligence/connections/')) {
        return const MockResponse(
          '{"offers":[{'
          '"code":"tavily","label":"Tavily",'
          '"description":"Recherche","can_connect":true,'
          '"capabilities":["web_research"],"requires_model":false'
          '}]}',
          200,
        );
      }
      throw StateError('No mutation expected');
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
    final space = SpaceActorIdentity(id: 'a', slug: 'alpha');
    final actor = await ActorContextController.restore(
      profileId: 'p1',
      store: _ActorStore(SpaceActorContext(space: space)),
    );
    addTearDown(actor.dispose);
    final runtime = AppRuntime(
      tokens: tokens,
      session: session,
      actorContext: actor,
      recovery: SessionRecoveryController(),
      api: api,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: SyncStatusScope(
          status: const SyncStatus(state: SyncVisualState.offline),
          child: SpaceConnectionsScreen(runtime: runtime, slug: 'alpha'),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Tavily'), findsOneWidget);
    expect(
      find.textContaining('Dernière observation uniquement'),
      findsOneWidget,
    );
    final tile = tester.widget<ListTile>(
      find.ancestor(of: find.text('Tavily'), matching: find.byType(ListTile)),
    );
    expect(tile.onTap, isNotNull);
    await tester.tap(find.text('Tavily'));
    await tester.pump();
    expect(find.byType(TextFormField), findsNothing);
    expect(find.textContaining('Ce service reste consultable'), findsOneWidget);
  });
}
