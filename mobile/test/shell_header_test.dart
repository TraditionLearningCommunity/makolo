import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/navigation/secondary_screen.dart';
import 'package:makolo_mobile/navigation/shell_header.dart';

void main() {
  testWidgets('Now header can expose a sober unread attention marker', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          appBar: MakoloPrimaryHeader(
            kind: MakoloHeaderKind.now,
            unreadNotifications: 3,
            onConversations: () {},
            onNotifications: () {},
            onAvatar: () {},
          ),
        ),
      ),
    );

    expect(find.text('Makolo'), findsOneWidget);
    expect(find.byTooltip('Conversations'), findsOneWidget);
    expect(find.byTooltip('Notifications, 3 non lues'), findsOneWidget);
    expect(find.byTooltip('Avatar'), findsOneWidget);
  });

  testWidgets('secondary back returns to the actual pushed origin', (
    tester,
  ) async {
    final router = GoRouter(
      initialLocation: '/origin',
      routes: [
        GoRoute(
          path: '/origin',
          builder: (context, state) => Scaffold(
            body: TextButton(
              onPressed: () => context.push('/detail'),
              child: const Text('Ouvrir détail'),
            ),
          ),
        ),
        GoRoute(
          path: '/detail',
          builder: (context, state) => const MakoloSecondaryScreen(
            title: 'Titre humain',
            message: 'Détail contextuel',
          ),
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp.router(theme: buildMakoloTheme(), routerConfig: router),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ouvrir détail'));
    await tester.pumpAndSettle();
    expect(find.text('Titre humain'), findsOneWidget);

    await tester.tap(find.byTooltip('Retour'));
    await tester.pumpAndSettle();
    expect(find.text('Ouvrir détail'), findsOneWidget);
  });
}
