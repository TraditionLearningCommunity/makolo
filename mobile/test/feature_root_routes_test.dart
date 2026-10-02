import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/mark/mark_screen.dart';
import 'package:makolo_mobile/features/me/me_screen.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/ongoing/ongoing_screen.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'fakes.dart';

Future<void> _pumpRoute(
  WidgetTester tester,
  AppRuntime runtime,
  String location,
) async {
  final router = createMakoloRouter(runtime, onAuthenticationChanged: () {});
  addTearDown(router.dispose);
  router.go(location);
  await tester.pumpWidget(
    MaterialApp.router(theme: buildMakoloTheme(), routerConfig: router),
  );
  await tester.pumpAndSettle();
}

void main() {
  late MakoloDatabase database;
  late AppRuntime runtime;

  setUp(() {
    database = MakoloDatabase.memory();
    final store = ProfileStore(database, 'profile-a');
    const session = AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    );
    runtime = AppRuntime(
      tokens: MemoryTokenStore(session: session),
      session: session,
      recovery: SessionRecoveryController(),
      database: database,
      store: store,
      personal: PersonalRepository(store),
    );
  });

  tearDown(() async {
    await database.close();
  });

  testWidgets('personal roots are owned by distinct feature screens', (
    tester,
  ) async {
    await _pumpRoute(tester, runtime, '/now');
    expect(find.byType(NowScreen), findsOneWidget);

    await _pumpRoute(tester, runtime, '/ongoing');
    expect(find.byType(OngoingScreen), findsOneWidget);

    await _pumpRoute(tester, runtime, '/me');
    expect(find.byType(MeScreen), findsOneWidget);

    await _pumpRoute(tester, runtime, '/mark');
    expect(find.byType(MarkScreen), findsOneWidget);
  });

  testWidgets('a Space root route does not grant a Space actor context', (
    tester,
  ) async {
    await _pumpRoute(tester, runtime, '/space/now');

    expect(find.byType(NowScreen), findsOneWidget);
    expect(find.text('Métier'), findsNothing);
    expect(find.text('Nous'), findsNothing);
  });

  testWidgets('depth routes remain registered after router fragmentation', (
    tester,
  ) async {
    await _pumpRoute(tester, runtime, '/journeys/journey-1');
    expect(
      find.text('Cette démarche n’est pas disponible sur cet appareil.'),
      findsOneWidget,
    );

    await _pumpRoute(tester, runtime, '/accesses/access-1');
    expect(
      find.text('Cet accès n’est pas disponible sur cet appareil.'),
      findsOneWidget,
    );

    await _pumpRoute(tester, runtime, '/occurrences/occurrence-1');
    expect(
      find.text('Cette occurrence n’est pas disponible sur cet appareil.'),
      findsOneWidget,
    );

    await _pumpRoute(tester, runtime, '/occurrences/occurrence-1/day-of');
    expect(
      find.text('Le Jour J n’est pas disponible sur cet appareil.'),
      findsOneWidget,
    );
  });

  testWidgets('unknown route uses the app fallback', (tester) async {
    await _pumpRoute(tester, runtime, '/not-a-makolo-route');
    expect(find.text('Cette page n’est pas disponible.'), findsOneWidget);
  });
}
