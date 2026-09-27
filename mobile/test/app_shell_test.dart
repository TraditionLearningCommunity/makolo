import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/app_shell.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/app/sync_lifecycle.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/mark/mark_screen.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

import 'fakes.dart';

AppRuntime _runtime(SessionRecoveryController recovery) =>
    AppRuntime(tokens: MemoryTokenStore(), session: null, recovery: recovery);

GoRouter _router(AppRuntime runtime) {
  return GoRouter(
    initialLocation: '/now',
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => AppShell(
          navigationShell: navigationShell,
          recovery: runtime.recovery,
          runtime: runtime,
        ),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/now',
                builder: (context, state) => const _TestTab(
                  label: 'Now content',
                  scrollKey: Key('now-scroll'),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/discover',
                builder: (context, state) =>
                    const _TestTab(label: 'Discover content'),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/ongoing',
                builder: (context, state) =>
                    const _TestTab(label: 'Ongoing content'),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/me',
                builder: (context, state) =>
                    const _TestTab(label: 'Me content'),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => MarkScreen(runtime: runtime),
      ),
      GoRoute(
        path: '/account',
        builder: (context, state) => const Scaffold(body: Text('Account')),
      ),
    ],
  );
}

Future<void> _pumpRouter(
  WidgetTester tester, {
  SyncStatus? status,
  Future<void> Function()? refresh,
  double textScale = 1,
}) async {
  final recovery = SessionRecoveryController();
  final runtime = _runtime(recovery);
  final router = _router(runtime);
  await tester.pumpWidget(
    MaterialApp.router(
      theme: buildMakoloTheme(),
      routerConfig: router,
      builder: (context, child) {
        Widget result = SyncRefreshScope(
          refresh: refresh ?? () async {},
          child: child ?? const SizedBox.shrink(),
        );
        if (status != null) {
          result = SyncStatusScope(status: status, child: result);
        }
        if (textScale != 1) {
          result = MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: TextScaler.linear(textScale)),
            child: result,
          );
        }
        return result;
      },
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('bottom navigation exposes four destinations plus Makolo Mark', (
    tester,
  ) async {
    await _pumpRouter(tester);

    expect(find.text('Now'), findsOneWidget);
    expect(find.text('Découvrir'), findsOneWidget);
    expect(find.text('En cours'), findsOneWidget);
    expect(find.text('Moi'), findsOneWidget);
    expect(find.byTooltip('Makolo Mark'), findsOneWidget);
    expect(find.byIcon(Icons.schedule_outlined), findsOneWidget);
    expect(find.byIcon(Icons.home_outlined), findsNothing);
  });

  testWidgets('touching a tab restores it without requesting refresh', (
    tester,
  ) async {
    var refreshes = 0;
    await _pumpRouter(
      tester,
      refresh: () async {
        refreshes += 1;
      },
    );

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Now'));
    await tester.pumpAndSettle();

    expect(refreshes, 0);
    expect(find.text('Now content'), findsOneWidget);
  });

  testWidgets('pull-to-refresh requests latest data without hiding content', (
    tester,
  ) async {
    final completer = Completer<void>();
    var refreshes = 0;
    await _pumpRouter(
      tester,
      refresh: () {
        refreshes += 1;
        return completer.future;
      },
    );

    await tester.drag(
      find.byKey(const Key('now-scroll')),
      const Offset(0, 320),
    );
    await tester.pump();

    expect(refreshes, 1);
    expect(find.text('Now content'), findsOneWidget);

    completer.complete();
    await tester.pumpAndSettle();
    expect(find.text('Now content'), findsOneWidget);
  });

  testWidgets('tab local state survives branch changes', (tester) async {
    await _pumpRouter(tester);

    await tester.tap(find.text('Incrémenter'));
    await tester.pump();
    expect(find.text('Compteur 1'), findsOneWidget);

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Now'));
    await tester.pumpAndSettle();

    expect(find.text('Compteur 1'), findsOneWidget);
  });

  testWidgets('tab scroll position survives branch changes', (tester) async {
    await _pumpRouter(tester);

    await tester.drag(
      find.byKey(const Key('now-scroll')),
      const Offset(0, -700),
    );
    await tester.pumpAndSettle();
    final before = tester
        .state<ScrollableState>(
          find.descendant(
            of: find.byKey(const Key('now-scroll')),
            matching: find.byType(Scrollable),
          ),
        )
        .position
        .pixels;
    expect(before, greaterThan(0));

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Now'));
    await tester.pumpAndSettle();

    final after = tester
        .state<ScrollableState>(
          find.descendant(
            of: find.byKey(const Key('now-scroll')),
            matching: find.byType(Scrollable),
          ),
        )
        .position
        .pixels;
    expect(after, closeTo(before, 0.1));
  });

  testWidgets('Mark is pushed and system back returns to the real origin', (
    tester,
  ) async {
    await _pumpRouter(tester);

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Makolo Mark'));
    await tester.pumpAndSettle();
    expect(find.text('Qu’est-ce que vous avez en tête ?'), findsOneWidget);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Ongoing content'), findsOneWidget);
  });

  testWidgets('main headers expose only tools for their current context', (
    tester,
  ) async {
    await _pumpRouter(tester);

    expect(find.byTooltip('Conversations'), findsOneWidget);
    expect(find.byTooltip('Notifications'), findsOneWidget);
    expect(find.byTooltip('Avatar'), findsOneWidget);
    expect(find.byTooltip('Rechercher'), findsNothing);

    await tester.tap(find.text('Découvrir'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Rechercher'), findsOneWidget);
    expect(find.byTooltip('Filtres'), findsOneWidget);
    expect(find.byTooltip('Conversations'), findsNothing);

    await tester.tap(find.text('En cours'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Calendrier'), findsOneWidget);
    expect(find.byTooltip('Notifications'), findsNothing);

    await tester.tap(find.text('Moi'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Avatar'), findsOneWidget);
    expect(find.byTooltip('Calendrier'), findsNothing);
  });

  testWidgets('Mark header is minimal', (tester) async {
    await _pumpRouter(tester);
    await tester.tap(find.byTooltip('Makolo Mark'));
    await tester.pumpAndSettle();

    expect(find.text('Makolo'), findsOneWidget);
    expect(find.byTooltip('Avatar'), findsOneWidget);
    expect(find.byTooltip('Notifications'), findsNothing);
    expect(find.byTooltip('Rechercher'), findsNothing);
  });

  testWidgets('offline and failed sync never replace existing content', (
    tester,
  ) async {
    await _pumpRouter(
      tester,
      status: const SyncStatus(state: SyncVisualState.offline),
    );
    expect(find.text('Now content'), findsOneWidget);
    expect(find.textContaining('Hors connexion'), findsOneWidget);

    await _pumpRouter(
      tester,
      status: const SyncStatus(state: SyncVisualState.failed),
    );
    expect(find.text('Now content'), findsOneWidget);
    expect(
      find.text('Impossible de mettre à jour pour le moment.'),
      findsOneWidget,
    );
  });

  testWidgets('shell remains usable with large text', (tester) async {
    await _pumpRouter(tester, textScale: 2);

    expect(tester.takeException(), isNull);
    expect(find.text('Now'), findsOneWidget);
    expect(find.byTooltip('Avatar'), findsOneWidget);
  });
}

class _TestTab extends StatefulWidget {
  const _TestTab({required this.label, this.scrollKey});

  final String label;
  final Key? scrollKey;

  @override
  State<_TestTab> createState() => _TestTabState();
}

class _TestTabState extends State<_TestTab> {
  int _count = 0;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      key: widget.scrollKey,
      itemCount: 60,
      itemBuilder: (context, index) {
        if (index == 0) return Text(widget.label);
        if (index == 1) {
          return TextButton(
            onPressed: () => setState(() => _count += 1),
            child: const Text('Incrémenter'),
          );
        }
        if (index == 2) return Text('Compteur $_count');
        return SizedBox(height: 48, child: Text('${widget.label} $index'));
      },
    );
  }
}
