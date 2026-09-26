import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/app_shell.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  testWidgets('shell exposes four destinations and the Makolo action', (
    tester,
  ) async {
    final router = GoRouter(
      initialLocation: '/now',
      routes: [
        ShellRoute(
          builder: (context, state, child) => AppShell(child: child),
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

    await tester.pumpWidget(
      MaterialApp.router(theme: buildMakoloTheme(), routerConfig: router),
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
  });

  testWidgets('offline banner preserves visible content', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Column(
          children: [
            OfflineBanner(),
            Expanded(child: Text('Contenu local conservé')),
          ],
        ),
      ),
    );

    expect(find.textContaining('Hors connexion'), findsOneWidget);
    expect(find.text('Contenu local conservé'), findsOneWidget);
  });

  testWidgets('empty state survives large text scale', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(2)),
          child: const MakoloEmptyState(
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
