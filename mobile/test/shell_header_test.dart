import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/navigation/secondary_screen.dart';
import 'package:makolo_mobile/navigation/shell_header.dart';

void main() {
  testWidgets('Now header exposes brand and sober unread attention marker', (
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

    expect(find.bySemanticsLabel('Makolo'), findsOneWidget);
    expect(find.byTooltip('Conversations'), findsOneWidget);
    expect(find.byTooltip('Notifications, 3 non lues'), findsOneWidget);
    expect(find.byTooltip('Avatar'), findsOneWidget);
  });


  testWidgets('brand lockup stays vector-sized under large text scaling', (
    tester,
  ) async {
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2.5)),
        child: MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            appBar: MakoloPrimaryHeader(
              kind: MakoloHeaderKind.now,
              onAvatar: () {},
            ),
          ),
        ),
      ),
    );

    final logo = tester.widget<SvgPicture>(find.byType(SvgPicture).first);
    expect(logo.height, 34);
    expect(find.text('Makolo'), findsNothing);
    expect(find.bySemanticsLabel('Makolo'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('brand lockup renders in dark mode without duplicate semantics', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        darkTheme: buildMakoloTheme(brightness: Brightness.dark),
        themeMode: ThemeMode.dark,
        home: Scaffold(
          appBar: MakoloPrimaryHeader(
            kind: MakoloHeaderKind.now,
            onAvatar: () {},
          ),
        ),
      ),
    );

    expect(find.byType(SvgPicture), findsOneWidget);
    expect(find.bySemanticsLabel('Makolo'), findsOneWidget);
    expect(find.text('Makolo'), findsNothing);
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
    expect(find.text('Titre humain'), findsOneWidget);

    await tester.tap(find.byTooltip('Retour'));
    await tester.pumpAndSettle();
    expect(find.text('Ouvrir détail'), findsOneWidget);
  });
}
