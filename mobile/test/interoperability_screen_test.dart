import 'dart:convert';
import 'dart:io';

import 'fakes.dart';
import 'dio_testing.dart';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';
import 'package:makolo_mobile/features/interoperability/connections_screen.dart';
import 'package:makolo_mobile/repositories/interoperability_repository.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

Future<AppRuntime> _runtimeWithPayload(
  Map<String, dynamic> payload, {
  required MakoloDatabase database,
}) async {
  final store = ProfileStore(database, 'profile-a');
  await store.putProjection(
    kind: ProfileInteroperabilityRepository.projectionKind,
    schemaVersion: 1,
    payload: payload,
  );
  return _runtimeWithStore(store, database);
}

AppRuntime _runtimeWithStore(ProfileStore store, MakoloDatabase database) {
  return AppRuntime(
    tokens: MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    ),
    session: const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    ),
    recovery: SessionRecoveryController(),
    database: database,
    store: store,
    interoperability: ProfileInteroperabilityRepository(store),
  );
}

Map<String, dynamic> _payload({
  List<Map<String, dynamic>> providers = const [],
  List<Map<String, dynamic>> connections = const [],
  List<Map<String, dynamic>> actions = const [],
  List<Map<String, dynamic>> extensions = const [],
}) {
  return {
    'schema_version': 'z16.v1',
    'context': 'profile',
    'providers': providers,
    'connections': connections,
    'actions': actions,
    'extensions': extensions,
    'webhooks': <Object>[],
    'links': {'self': '/api/v1/me/interoperability/'},
  };
}

Future<void> _unmount(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump(const Duration(seconds: 1));
}

void main() {
  testWidgets('Profile Connexions renders a stable honest empty state', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final runtime = await _runtimeWithPayload(_payload(), database: database);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Connexions'), findsOneWidget);
    expect(find.text('Découvrir'), findsOneWidget);
    expect(find.text('Mes connexions'), findsOneWidget);
    expect(
      find.textContaining('Service Connexions indisponible'),
      findsOneWidget,
    );
    expect(find.textContaining('Marketplace'), findsNothing);
    expect(find.textContaining('Connecter'), findsNothing);

    await _unmount(tester);
  });

  testWidgets(
    'Profile Connexions keeps scopes isolated and humanizes capabilities',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final runtime = await _runtimeWithPayload(
        _payload(
          connections: [
            {
              'id': 'profile-connection',
              'scope': 'profile',
              'owner': 'intelligence',
              'provider_protocol': 'openai_compatible',
              'display_name': 'Mon service',
              'available': true,
              'connected': true,
              'usable': true,
              'manageable': true,
              'enabled': true,
              'status': 'connected',
              'health': 'healthy',
              'capabilities': ['text_generate'],
              'permissions': {'use': true, 'manage': true},
              'encrypted_secret': 'never-render-me',
            },
            {
              'id': 'space-connection',
              'scope': 'space',
              'owner': 'intelligence',
              'provider_protocol': 'openai_compatible',
              'display_name': 'Service Espace',
              'available': true,
              'connected': true,
              'usable': true,
              'manageable': true,
              'enabled': true,
              'status': 'connected',
              'health': 'healthy',
              'capabilities': ['text_generate'],
              'permissions': {'use': true, 'manage': true},
            },
          ],
        ),
        database: database,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: ProfileConnectionsScreen(runtime: runtime),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('Mon service'), findsOneWidget);
      await tester.tap(find.text('Mon service'));
      await tester.pump();
      expect(find.text('Ce service est prêt à être utilisé.'), findsOneWidget);
      expect(find.textContaining('Connecté et disponible'), findsOneWidget);
      expect(find.textContaining('Génération de texte'), findsOneWidget);
      expect(find.text('Service Espace'), findsNothing);
      expect(find.textContaining('never-render-me'), findsNothing);
      expect(find.textContaining('openai_compatible'), findsNothing);
      expect(find.textContaining('text_generate'), findsNothing);
      expect(find.textContaining('Déconnecter'), findsNothing);

      await _unmount(tester);
    },
  );

  testWidgets('Profile Connexions preserves distinct connection states', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final runtime = await _runtimeWithPayload(
      _payload(
        connections: [
          {
            'id': 'disabled',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'protocol',
            'display_name': 'Service désactivé',
            'available': true,
            'connected': true,
            'usable': false,
            'manageable': true,
            'enabled': false,
            'status': 'disabled',
            'health': 'healthy',
            'capabilities': <String>[],
            'permissions': {'use': false, 'manage': true},
          },
          {
            'id': 'degraded',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'protocol',
            'display_name': 'Service dégradé',
            'available': true,
            'connected': true,
            'usable': true,
            'manageable': true,
            'enabled': true,
            'status': 'connected',
            'health': 'degraded',
            'capabilities': <String>[],
            'permissions': {'use': true, 'manage': true},
          },
          {
            'id': 'unavailable',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'protocol',
            'display_name': 'Service indisponible',
            'available': true,
            'connected': true,
            'usable': false,
            'manageable': true,
            'enabled': true,
            'status': 'connected',
            'health': 'unavailable',
            'capabilities': <String>[],
            'permissions': {'use': false, 'manage': true},
          },
          {
            'id': 'unknown',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'protocol',
            'display_name': 'Service à vérifier',
            'available': true,
            'connected': true,
            'usable': false,
            'manageable': true,
            'enabled': true,
            'status': 'connected',
            'health': 'unknown',
            'capabilities': <String>[],
            'permissions': {'use': false, 'manage': true},
          },
        ],
      ),
      database: database,
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Désactivé'), findsOneWidget);
    expect(find.text('Connecté · disponibilité réduite'), findsOneWidget);
    expect(find.text('Momentanément indisponible'), findsOneWidget);
    expect(find.text('Connecté · état à vérifier'), findsOneWidget);
    await tester.tap(find.text('Service désactivé'));
    await tester.pump();
    expect(find.text('Cette connexion est désactivée.'), findsOneWidget);
    await tester.pageBack();
    await tester.pump();
    await tester.tap(find.text('Service indisponible'));
    await tester.pump();
    expect(find.text('Le service ne répond pas actuellement.'), findsOneWidget);
    await tester.pageBack();
    await tester.pump();
    await tester.tap(find.text('Service à vérifier'));
    await tester.pump();
    expect(find.text('La disponibilité doit être vérifiée.'), findsOneWidget);

    await _unmount(tester);
  });

  testWidgets('Profile Connexions renders authorized actions and extensions', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final runtime = await _runtimeWithPayload(
      _payload(
        providers: [
          {
            'code': 'provider_internal_code',
            'available': true,
            'capabilities': ['text_generate'],
          },
        ],
        actions: [
          {
            'code': 'calendar.create',
            'capability': 'calendar.write',
            'owner': 'activities',
            'requires_connection': true,
            'available': false,
            'authorized': true,
            'idempotency_required': true,
          },
          {
            'code': 'private.denied',
            'capability': 'private',
            'owner': 'private',
            'requires_connection': false,
            'available': true,
            'authorized': false,
            'idempotency_required': false,
          },
        ],
        extensions: [
          {
            'code': 'profile.helper',
            'actions': ['calendar.create'],
            'read_projections': <String>[],
            'ui_slots': <String>[],
            'available': true,
            'enabled': true,
          },
        ],
      ),
      database: database,
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    // Registry metadata is not a connectable owner offer. Never display
    // executable-looking cards for it in the personal connection catalogue.
    expect(find.text('Service disponible'), findsNothing);
    expect(find.text('Calendar create'), findsNothing);
    expect(find.text('Private denied'), findsNothing);
    expect(find.text('Profile helper'), findsNothing);
    expect(find.textContaining('provider_internal_code'), findsNothing);
    expect(find.byType(FilledButton), findsNothing);

    await _unmount(tester);
  });

  testWidgets('personal Intelligence shows a real Discovery continuation', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final runtime = await _runtimeWithPayload(
      _payload(
        connections: [
          {
            'id': 'research',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'tavily_search',
            'display_name': 'Recherche externe',
            'available': true,
            'connected': true,
            'usable': true,
            'manageable': true,
            'enabled': true,
            'status': 'connected',
            'health': 'unknown',
            'capabilities': ['web_research'],
          },
          {
            'id': 'space',
            'scope': 'space',
            'owner': 'intelligence',
            'provider_protocol': 'tavily_search',
            'display_name': 'Service autre contexte',
            'available': true,
            'connected': true,
            'usable': true,
            'manageable': true,
            'enabled': true,
            'status': 'connected',
            'health': 'healthy',
            'capabilities': ['web_research'],
          },
        ],
      ),
      database: database,
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Recherche externe'), findsOneWidget);
    expect(find.text('Service autre contexte'), findsNothing);
    await tester.tap(find.text('Recherche externe'));
    await tester.pump();
    expect(
      find.byKey(const Key('discover-from-connection-research')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('discover-from-connection-space')),
      findsNothing,
    );
    await _unmount(tester);
  });

  testWidgets('offline cached connections remain visible without explanation', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final runtime = await _runtimeWithPayload(
      _payload(
        connections: [
          {
            'id': 'cached',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'protocol',
            'display_name': 'Service en cache',
            'available': true,
            'connected': true,
            'usable': true,
            'manageable': true,
            'enabled': true,
            'status': 'connected',
            'health': 'healthy',
            'capabilities': <String>[],
            'permissions': {'use': true, 'manage': true},
          },
        ],
      ),
      database: database,
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: SyncStatusScope(
          status: const SyncStatus(state: SyncVisualState.offline),
          child: ProfileConnectionsScreen(runtime: runtime),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Service en cache'), findsOneWidget);
    expect(
      find.textContaining('Dernier état connu'),
      findsNothing,
    );

    await _unmount(tester);
  });

  testWidgets('offline without cache degrades only Connexions', (tester) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final runtime = _runtimeWithStore(store, database);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: SyncStatusScope(
          status: const SyncStatus(state: SyncVisualState.offline),
          child: ProfileConnectionsScreen(runtime: runtime),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Aucune connexion disponible.'), findsOneWidget);
    expect(
      find.byKey(const Key('profile-connections-offline-empty')),
      findsOneWidget,
    );

    await _unmount(tester);
  });

  testWidgets('refresh uses Z16 and retains a known connection after failure', (
    tester,
  ) async {
    var online = true;
    var serviceName = 'Service initial';
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/me/interoperability/');
      if (!online) throw const SocketException('offline');
      return MockResponse(
        jsonEncode(
          _payload(
            connections: [
              {
                'id': 'personal-connection',
                'scope': 'profile',
                'owner': 'intelligence',
                'provider_protocol': 'openai_compatible',
                'display_name': serviceName,
                'available': true,
                'connected': true,
                'usable': true,
                'manageable': true,
                'enabled': true,
                'status': 'connected',
                'health': 'healthy',
                'capabilities': ['text_generate'],
              },
            ],
          ),
        ),
        200,
      );
    });
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      dio: client.dio,
      tokenStore: tokens,
    );
    addTearDown(api.close);
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final sync = SyncEngine(
      api: api,
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    final runtime = AppRuntime(
      tokens: tokens,
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
      recovery: SessionRecoveryController(),
      database: database,
      store: store,
      interoperability: ProfileInteroperabilityRepository(store),
      sync: sync,
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    await tester.tap(find.text('Mes connexions'));
    await tester.pump();
    expect(find.text('Service initial'), findsOneWidget);

    serviceName = 'Service actualisé';
    await tester.tap(find.byTooltip('Actualiser les connexions'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Service actualisé'), findsOneWidget);
    expect(find.text('Service initial'), findsNothing);

    online = false;
    await tester.tap(find.byTooltip('Actualiser les connexions'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    expect(find.text('Service actualisé'), findsOneWidget);
    expect(
      find.text(
        'Actualisation impossible. Le dernier état connu est conservé.',
      ),
      findsOneWidget,
    );

    await _unmount(tester);
  });

  testWidgets('an absent projection without a sync owner never spins forever', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final runtime = _runtimeWithStore(store, database);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(
      find.text('Impossible de vérifier vos connexions pour le moment.'),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.text('Aucune connexion pour le moment'), findsNothing);

    await _unmount(tester);
  });

  testWidgets('wide and text scale remain a readable pane', (tester) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final runtime = await _runtimeWithPayload(
      _payload(
        connections: [
          {
            'id': 'wide',
            'scope': 'profile',
            'owner': 'intelligence',
            'provider_protocol': 'protocol',
            'display_name': 'Service large',
            'available': true,
            'connected': true,
            'usable': true,
            'manageable': false,
            'enabled': true,
            'status': 'connected',
            'health': 'healthy',
            'capabilities': ['text_generate'],
            'permissions': {'use': true, 'manage': false},
          },
        ],
      ),
      database: database,
    );

    await tester.binding.setSurfaceSize(const Size(1400, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
          child: ProfileConnectionsScreen(runtime: runtime),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Service large'), findsOneWidget);
    expect(find.textContaining('Génération de texte'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await _unmount(tester);
  });
}
