import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

abstract final class PresentationHarness {
  static Future<void> pump(
    WidgetTester tester, {
    required Widget child,
    Size viewport = const Size(360, 800),
    Brightness brightness = Brightness.light,
    double textScale = 1,
    bool reduceMotion = false,
  }) async {
    tester.view.physicalSize = viewport;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: buildMakoloLightTheme(),
        darkTheme: buildMakoloDarkTheme(),
        themeMode: brightness == Brightness.dark
            ? ThemeMode.dark
            : ThemeMode.light,
        home: MediaQuery(
          data: MediaQueryData(
            size: viewport,
            textScaler: TextScaler.linear(textScale),
            disableAnimations: reduceMotion,
          ),
          child: Scaffold(body: child),
        ),
      ),
    );
    await tester.pump();
  }
}
