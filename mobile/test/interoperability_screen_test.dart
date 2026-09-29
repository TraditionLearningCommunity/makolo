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

import 'fakes.dart';

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

void main() {
  testWidgets('Profile Connexions renders a stable empty state', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtimeWithPayload(_payload(), database: database);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: ProfileConnectionsScreen(runtime: runtime),
      ),
    );
    // Drift-backed streams stay live by design. Wait only for the first
    // projection frame instead of asking the whole app to become quiescent.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Connexions'), findsOneWidget);
    expect(find.text('Aucune connexion pour le moment'), findsOneWidget);
    expect(
      find.textContaining('Aucun service ni aucune extension'),
      findsOneWidget,
    );
    // Unmount the StreamBuilder so its Drift subscription is cancelled before
    // the test ends. Do not close the in-memory database here: Drift can wait
    // for the just-cancelled watcher while the widget test fake clock is no
    // longer advancing, which is exactly the lifecycle deadlock this
    // regression test protects against.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 1));
  });

  testWidgets('Profile Connexions shows only Profile connections', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
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
    // Drift-backed streams stay live by design. Wait only for the first
    // projection frame instead of asking the whole app to become quiescent.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Mon service'), findsOneWidget);
    expect(find.text('Connecté et disponible'), findsOneWidget);
    expect(find.text('Service Espace'), findsNothing);
    expect(find.textContaining('never-render-me'), findsNothing);
    // Unmount the StreamBuilder so its Drift subscription is cancelled before
    // the test ends. Do not close the in-memory database here: Drift can wait
    // for the just-cancelled watcher while the widget test fake clock is no
    // longer advancing, which is exactly the lifecycle deadlock this
    // regression test protects against.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 1));
  });

  testWidgets('Profile Connexions renders authorized actions and extensions', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final runtime = await _runtimeWithPayload(
      _payload(
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
    // Drift-backed streams stay live by design. Wait only for the first
    // projection frame instead of asking the whole app to become quiescent.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Calendar create'), findsOneWidget);
    expect(find.text('Connexion requise'), findsOneWidget);
    expect(find.text('Private denied'), findsNothing);
    expect(find.text('Profile helper'), findsOneWidget);
    // Unmount the StreamBuilder so its Drift subscription is cancelled before
    // the test ends. Do not close the in-memory database here: Drift can wait
    // for the just-cancelled watcher while the widget test fake clock is no
    // longer advancing, which is exactly the lifecycle deadlock this
    // regression test protects against.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 1));
  });
}
