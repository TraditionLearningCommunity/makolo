import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/app_shell.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

GoRouter _router(SessionRecoveryController recovery) {
  return GoRouter(
    initialLocation: '/now',
    routes: [
      ShellRoute(
        builder: (context, state, child) => AppShell(
          recovery: recovery,
          child: child,
        ),
        routes: [
          for (final path in const ['/now', '/discover', '/ongoing', '/me'])
            GoRoute(path: path, builder: (context, state) => Text(path)),
        ],
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => const Text('Mark intake'),
      ),
    ],
  );
}

void main() {
  testWidgets('shell exposes four destinations and the Makolo action', (
    tester,
  ) async {
    final recovery = SessionRecoveryController();
    final router = _router(recovery);

    await tester.pumpWidget(
      MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Maintenant'), findsOneWidget);
    expect(find.text('Découvrir'), findsOneWidget);
    expect(find.text('En cours'), findsOneWidget);
    expect(find.text('Moi'), findsOneWidget);
    expect(find.byTooltip('Makolo'), findsOneWidget);

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    expect(find.text('/ongoing'), findsOneWidget);
    expect(recovery.lastUsefulLocation, '/ongoing');
  });

  testWidgets('Mark preserves navigation history for system back', (
    tester,
  ) async {
    final router = _router(SessionRecoveryController());

    await tester.pumpWidget(
      MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Makolo'));
    await tester.pumpAndSettle();
    expect(find.text('Mark intake'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('/ongoing'), findsOneWidget);
  });

  testWidgets('content remains visible while offline', (tester) async {
    final router = _router(SessionRecoveryController());

    await tester.pumpWidget(
      MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
        builder: (context, child) => SyncStatusScope(
          status: const SyncStatus(state: SyncVisualState.offline),
          child: child ?? const SizedBox.shrink(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('/now'), findsOneWidget);
    expect(find.text('Hors connexion'), findsOneWidget);
  });

  testWidgets('content remains visible while synchronization is pending', (
    tester,
  ) async {
    final router = _router(SessionRecoveryController());

    await tester.pumpWidget(
      MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
        builder: (context, child) => SyncStatusScope(
          status: const SyncStatus(
            state: SyncVisualState.pending,
            pendingCount: 1,
          ),
          child: child ?? const SizedBox.shrink(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('/now'), findsOneWidget);
    expect(find.text('En attente de synchronisation'), findsOneWidget);
  });

  testWidgets('empty state survives large text scale', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(2)),
          child: MakoloEmptyState(
            title: 'Tout est en ordre. ✓',
            body: 'Aucune action nécessaire.',
          ),
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(find.text('Tout est en ordre. ✓'), findsOneWidget);
  });
}
