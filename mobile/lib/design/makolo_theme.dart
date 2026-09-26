import 'package:flutter/material.dart';

abstract final class MakoloColors {
  static const indigo = Color(0xFF5232DB);
  static const deep = Color(0xFF2B176E);
  static const pulse = Color(0xFFFF704D);
  static const warm = Color(0xFFFAF7F5);
  static const ink = Color(0xFF0F172A);
  static const success = Color(0xFF07806F);
  static const warning = Color(0xFFB45309);
  static const danger = Color(0xFFC83C3C);
  static const info = Color(0xFF2563EB);
}

abstract final class MakoloSpacing {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}

abstract final class MakoloRadii {
  static const small = 10.0;
  static const medium = 16.0;
  static const large = 24.0;
}

abstract final class MakoloMotion {
  static const short = Duration(milliseconds: 160);
  static const medium = Duration(milliseconds: 240);

  static Duration effective(BuildContext context, Duration duration) {
    return MediaQuery.maybeOf(context)?.disableAnimations == true
        ? Duration.zero
        : duration;
  }
}

ThemeData buildMakoloTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: MakoloColors.indigo,
    brightness: Brightness.light,
  ).copyWith(
    primary: MakoloColors.indigo,
    secondary: MakoloColors.pulse,
    surface: MakoloColors.warm,
    onSurface: MakoloColors.ink,
    error: MakoloColors.danger,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: MakoloColors.warm,
    textTheme: const TextTheme(
      headlineSmall: TextStyle(
        fontFamily: 'Manrope',
        fontFamilyFallback: ['sans-serif'],
        fontWeight: FontWeight.w700,
      ),
      titleLarge: TextStyle(
        fontFamily: 'Manrope',
        fontFamilyFallback: ['sans-serif'],
        fontWeight: FontWeight.w700,
      ),
      bodyLarge: TextStyle(
        fontFamily: 'Inter',
        fontFamilyFallback: ['sans-serif'],
      ),
      bodyMedium: TextStyle(
        fontFamily: 'Inter',
        fontFamilyFallback: ['sans-serif'],
      ),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      height: 72,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
    ),
  );
}
