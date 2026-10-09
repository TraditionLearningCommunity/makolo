import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/interoperability/connections_screen.dart';
import 'package:makolo_mobile/repositories/interoperability_repository.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

Future<AppRuntime> _runtime({
  Map<String, dynamic>? payload,
  required MakoloDatabase database,
}) async {
  final store = ProfileStore(database, 'profile-a');
  if (payload != null) {
    await store.putProjection(
      kind: ProfileInteroperabilityRepository.projectionKind,
      schemaVersion: 1,
      payload: payload,
    );
  }
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

Future<void> _pump(
  WidgetTester tester,
  AppRuntime runtime, {
  SyncStatus? status,
  Size size = const Size(800, 900),
}) async {
  await tester.binding.setSurfaceSize(size);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  Widget child = ProfileConnectionsScreen(runtime: runtime);
  if (status != null) {
    child = SyncStatusScope(status: status, child: child);
  }
  await tester.pumpWidget(
    MaterialApp(theme: buildMakoloTheme(), home: child),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
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
    final runtime = await _runtime(payload: _payload(), database: database);

    await _pump(tester, runtime);

    expect(find.text('Connexions'), findsOneWidget);
    expect(find.text('Aucune connexion pour le moment'), findsOneWidget);
    expect(
      find.text('Aucun service n’est encore disponible pour votre Profil.'),
      findsOneWidget,
    );
    expect(find.textContaining('Marketplace'), findsNothing);
    expect(find.textContaining('Connecter'), findsNothing);

    await _unmount(tester);
  });

  testWidgets('Profile Connexions keeps scopes isolated and humanizes capabilities', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtime(
      payload: _payload(
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

    await _pump(tester, runtime);

    expect(find.text('Mon service'), findsOneWidget);
    expect(find.text('Connecté et disponible'), findsOneWidget);
    expect(find.text('Génération de texte'), findsOneWidget);
    expect(find.text('Service Espace'), findsNothing);
    expect(find.textContaining('never-render-me'), findsNothing);
    expect(find.textContaining('openai_compatible'), findsNothing);
    expect(find.textContaining('text_generate'), findsNothing);
    expect(find.textContaining('Déconnecter'), findsNothing);

    await _unmount(tester);
  });

  testWidgets('Profile Connexions preserves disabled degraded unavailable and unknown', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    Map<String, dynamic> row(
      String id,
      String name, {
      bool enabled = true,
      String health = 'healthy',
      bool usable = false,
    }) {
      return {
        'id': id,
        'scope': 'profile',
        'owner': 'intelligence',
        'provider_protocol': 'protocol',
        'display_name': name,
        'available': true,
        'connected': true,
        'usable': usable,
        'manageable': true,
        'enabled': enabled,
        'status': enabled ? 'connected' : 'disabled',
        'health': health,
        'capabilities': <String>[],
        'permissions': {'use': usable, 'manage': true},
      };
    }

    final runtime = await _runtime(
      payload: _payload(
        connections: [
          row('disabled', 'Service désactivé', enabled: false),
          row('degraded', 'Service dégradé', health: 'degraded'),
          row('unavailable', 'Service indisponible', health: 'unavailable'),
          row('unknown', 'Service à vérifier', health: 'unknown'),
        ],
      ),
      database: database,
    );

    await _pump(tester, runtime);

    expect(find.text('Désactivé'), findsOneWidget);
    expect(find.text('Connecté · disponibilité réduite'), findsOneWidget);
    expect(find.text('Momentanément indisponible'), findsOneWidget);
    expect(find.text('Connecté · état à vérifier'), findsOneWidget);

    await _unmount(tester);
  });

  testWidgets('Profile Connexions renders authorized actions and allowlisted extensions', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtime(
      payload: _payload(
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

    await _pump(tester, runtime);

    expect(find.text('Service disponible'), findsOneWidget);
    expect(find.textContaining('provider_internal_code'), findsNothing);
    expect(find.text('Calendar create'), findsOneWidget);
    expect(find.text('Connexion requise'), findsOneWidget);
    expect(find.text('Private denied'), findsNothing);
    expect(find.text('Profile helper'), findsOneWidget);

    await _unmount(tester);
  });

  testWidgets('offline cached projection is explicitly last-known', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtime(
      payload: _payload(
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

    await _pump(
      tester,
      runtime,
      status: const SyncStatus(state: SyncVisualState.offline),
    );

    expect(find.text('Service en cache'), findsOneWidget);
    expect(
      find.text('Dernier état connu. La disponibilité actuelle peut avoir changé.'),
      findsOneWidget,
    );

    await _unmount(tester);
  });

  testWidgets('offline without cache degrades only Connexions', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtime(database: database);

    await _pump(
      tester,
      runtime,
      status: const SyncStatus(state: SyncVisualState.offline),
    );

    expect(find.text('Connexions indisponibles hors ligne'), findsOneWidget);
    expect(
      find.textContaining('Le reste de Makolo continue de fonctionner'),
      findsOneWidget,
    );

    await _unmount(tester);
  });

  testWidgets('wide and text scale remain a single readable pane', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtime(
      payload: _payload(
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
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(1.6)),
          child: child!,
        ),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Service large'), findsOneWidget);
    expect(find.text('Génération de texte'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await _unmount(tester);
  });
}
