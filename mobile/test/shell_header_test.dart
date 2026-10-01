import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/design/makolo_mark.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/navigation/secondary_screen.dart';
import 'package:makolo_mobile/navigation/shell_header.dart';

void main() {
  testWidgets('Maintenant keeps the full Makolo brand', (tester) async {
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

    expect(find.byType(SvgPicture), findsOneWidget);
    expect(find.bySemanticsLabel('Makolo'), findsOneWidget);
    expect(find.byTooltip('Conversations'), findsOneWidget);
    expect(find.byTooltip('Notifications, 3 non lues'), findsOneWidget);
    expect(find.byTooltip('Avatar'), findsOneWidget);
  });

  testWidgets('Découvrir is Mark plus title with Search and Map', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          appBar: MakoloPrimaryHeader(
            kind: MakoloHeaderKind.discover,
            onSearch: () {},
            onMap: () {},
            onAvatar: () {},
          ),
        ),
      ),
    );

    expect(find.byType(MakoloMark), findsOneWidget);
    expect(find.text('Découvrir'), findsOneWidget);
    expect(find.byTooltip('Rechercher'), findsOneWidget);
    expect(find.byTooltip('Carte'), findsOneWidget);
    expect(find.byTooltip('Filtres'), findsNothing);
  });

  testWidgets('main door header fits a small phone at large text', (tester) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(2)),
          child: Scaffold(
            appBar: MakoloPrimaryHeader(
              kind: MakoloHeaderKind.me,
              onAvatar: () {},
            ),
          ),
        ),
      ),
    );

    expect(find.text('Moi'), findsOneWidget);
    expect(find.byType(MakoloMark), findsOneWidget);
    expect(tester.takeException(), isNull);
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

    await tester.tap(find.byTooltip('Retour'));
    await tester.pumpAndSettle();
    expect(find.text('Ouvrir détail'), findsOneWidget);
  });
}
