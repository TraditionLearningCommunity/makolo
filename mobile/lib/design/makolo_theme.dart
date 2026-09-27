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

  static const lightSurfaceLow = Color(0xFFFDFBFA);
  static const lightSurface = Color(0xFFFFFFFF);
  static const lightSurfaceRaised = Color(0xFFFFFFFF);
  static const lightBorder = Color(0xFFE7E1DD);
  static const lightMuted = Color(0xFF64748B);

  static const darkSurfaceLow = Color(0xFF151E32);
  static const darkSurface = Color(0xFF1B2438);
  static const darkSurfaceRaised = Color(0xFF232D43);
  static const darkBorder = Color(0xFF334155);
  static const darkMuted = Color(0xFFB8C2D1);
}

abstract final class MakoloSpacing {
  static const micro = 4.0;
  static const xs = micro;
  static const sm = 8.0;
  static const compact = 12.0;
  static const md = 16.0;
  static const inner = 20.0;
  static const lg = 24.0;
  static const xl = 32.0;
  static const strong = 40.0;
  static const structure = 48.0;
  static const exceptional = 64.0;
}

abstract final class MakoloRadii {
  static const control = 12.0;
  static const small = control;
  static const card = 16.0;
  static const medium = card;
  static const large = 24.0;
  static const sheet = 28.0;
  static const pill = 999.0;
}

abstract final class MakoloLayout {
  static const screenMargin = 20.0;
  static const compactScreenMargin = 16.0;
  static const navigationRailMinWidth = 840.0;
  static const navigationRailMinHeight = 480.0;
  static const navigationRailWidth = 104.0;

  static bool useNavigationRail(Size size) {
    return size.width >= navigationRailMinWidth &&
        size.height >= navigationRailMinHeight;
  }
}

abstract final class MakoloElevation {
  static const level0 = 0.0;
  static const level1 = 1.0;
  static const level2 = 4.0;
}

abstract final class MakoloMotion {
  static const instant = Duration(milliseconds: 120);
  static const short = Duration(milliseconds: 160);
  static const medium = Duration(milliseconds: 240);
  static const structural = Duration(milliseconds: 320);

  static Duration effective(BuildContext context, Duration duration) {
    return MediaQuery.maybeOf(context)?.disableAnimations == true
        ? Duration.zero
        : duration;
  }
}

@immutable
class MakoloSurfaces extends ThemeExtension<MakoloSurfaces> {
  const MakoloSurfaces({
    required this.canvas,
    required this.low,
    required this.surface,
    required this.raised,
    required this.brand,
    required this.border,
    required this.success,
    required this.warning,
    required this.info,
  });

  final Color canvas;
  final Color low;
  final Color surface;
  final Color raised;
  final Color brand;
  final Color border;
  final Color success;
  final Color warning;
  final Color info;

  static const light = MakoloSurfaces(
    canvas: MakoloColors.warm,
    low: MakoloColors.lightSurfaceLow,
    surface: MakoloColors.lightSurface,
    raised: MakoloColors.lightSurfaceRaised,
    brand: MakoloColors.indigo,
    border: MakoloColors.lightBorder,
    success: MakoloColors.success,
    warning: MakoloColors.warning,
    info: MakoloColors.info,
  );

  static const dark = MakoloSurfaces(
    canvas: MakoloColors.ink,
    low: MakoloColors.darkSurfaceLow,
    surface: MakoloColors.darkSurface,
    raised: MakoloColors.darkSurfaceRaised,
    brand: MakoloColors.deep,
    border: MakoloColors.darkBorder,
    success: MakoloColors.success,
    warning: MakoloColors.warning,
    info: MakoloColors.info,
  );

  @override
  MakoloSurfaces copyWith({
    Color? canvas,
    Color? low,
    Color? surface,
    Color? raised,
    Color? brand,
    Color? border,
    Color? success,
    Color? warning,
    Color? info,
  }) {
    return MakoloSurfaces(
      canvas: canvas ?? this.canvas,
      low: low ?? this.low,
      surface: surface ?? this.surface,
      raised: raised ?? this.raised,
      brand: brand ?? this.brand,
      border: border ?? this.border,
      success: success ?? this.success,
      warning: warning ?? this.warning,
      info: info ?? this.info,
    );
  }

  @override
  MakoloSurfaces lerp(covariant MakoloSurfaces? other, double t) {
    if (other == null) return this;
    return MakoloSurfaces(
      canvas: Color.lerp(canvas, other.canvas, t)!,
      low: Color.lerp(low, other.low, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      raised: Color.lerp(raised, other.raised, t)!,
      brand: Color.lerp(brand, other.brand, t)!,
      border: Color.lerp(border, other.border, t)!,
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      info: Color.lerp(info, other.info, t)!,
    );
  }
}

extension MakoloThemeContext on BuildContext {
  MakoloSurfaces get makoloSurfaces =>
      Theme.of(this).extension<MakoloSurfaces>()!;
}

const _lightScheme = ColorScheme.light(
  primary: MakoloColors.indigo,
  onPrimary: Colors.white,
  primaryContainer: Color(0xFFE9E4FF),
  onPrimaryContainer: MakoloColors.deep,
  secondary: MakoloColors.deep,
  onSecondary: Colors.white,
  secondaryContainer: Color(0xFFF0ECFF),
  onSecondaryContainer: MakoloColors.deep,
  tertiary: MakoloColors.pulse,
  onTertiary: MakoloColors.ink,
  tertiaryContainer: Color(0xFFFFE5DE),
  onTertiaryContainer: MakoloColors.ink,
  error: MakoloColors.danger,
  onError: Colors.white,
  errorContainer: Color(0xFFFFE8E7),
  onErrorContainer: Color(0xFF5F1515),
  surface: MakoloColors.lightSurface,
  onSurface: MakoloColors.ink,
  surfaceContainerHighest: Color(0xFFF1ECE9),
  onSurfaceVariant: MakoloColors.lightMuted,
  outline: Color(0xFF8A7E78),
  outlineVariant: MakoloColors.lightBorder,
  shadow: Color(0x290F172A),
  scrim: Color(0x660F172A),
  inverseSurface: MakoloColors.ink,
  onInverseSurface: MakoloColors.warm,
  inversePrimary: Color(0xFFB9ACFF),
);

const _darkScheme = ColorScheme.dark(
  primary: MakoloColors.indigo,
  onPrimary: Colors.white,
  primaryContainer: MakoloColors.deep,
  onPrimaryContainer: MakoloColors.warm,
  secondary: Color(0xFFB9ACFF),
  onSecondary: MakoloColors.ink,
  secondaryContainer: Color(0xFF342660),
  onSecondaryContainer: MakoloColors.warm,
  tertiary: MakoloColors.pulse,
  onTertiary: MakoloColors.ink,
  tertiaryContainer: Color(0xFF5B2A21),
  onTertiaryContainer: Color(0xFFFFE5DE),
  error: Color(0xFFFFB4AB),
  onError: Color(0xFF690005),
  errorContainer: Color(0xFF93000A),
  onErrorContainer: Color(0xFFFFDAD6),
  surface: MakoloColors.darkSurface,
  onSurface: MakoloColors.warm,
  surfaceContainerHighest: MakoloColors.darkSurfaceRaised,
  onSurfaceVariant: MakoloColors.darkMuted,
  outline: Color(0xFF8D98AA),
  outlineVariant: MakoloColors.darkBorder,
  shadow: Colors.black,
  scrim: Color(0x99000000),
  inverseSurface: MakoloColors.warm,
  onInverseSurface: MakoloColors.ink,
  inversePrimary: MakoloColors.deep,
);

TextTheme _makoloTextTheme(Color foreground) {
  TextStyle manrope({
    required double size,
    required FontWeight weight,
    double? height,
  }) => TextStyle(
    fontSize: size,
    fontWeight: weight,
    height: height,
    color: foreground,
  );

  TextStyle inter({
    required double size,
    required FontWeight weight,
    double? height,
  }) => TextStyle(
    fontSize: size,
    fontWeight: weight,
    height: height,
    color: foreground,
  );

  // Manrope and Inter are intentionally not named here until their official
  // local font assets are available in the repository. Flutter therefore uses
  // the platform sans-serif fallback while preserving the canonical scale.
  return TextTheme(
    displayLarge: manrope(size: 32, weight: FontWeight.w800, height: 1.18),
    headlineLarge: manrope(size: 28, weight: FontWeight.w800, height: 1.2),
    headlineMedium: manrope(size: 24, weight: FontWeight.w700, height: 1.24),
    headlineSmall: manrope(size: 20, weight: FontWeight.w700, height: 1.28),
    titleLarge: manrope(size: 17, weight: FontWeight.w700, height: 1.3),
    bodyLarge: inter(size: 16, weight: FontWeight.w400, height: 1.5),
    bodyMedium: inter(size: 14, weight: FontWeight.w400, height: 1.45),
    labelLarge: inter(size: 13, weight: FontWeight.w600, height: 1.3),
    bodySmall: inter(size: 12, weight: FontWeight.w500, height: 1.4),
    labelMedium: inter(size: 11, weight: FontWeight.w600, height: 1.25),
  );
}

ThemeData _buildTheme({
  required Brightness brightness,
  required ColorScheme scheme,
  required MakoloSurfaces surfaces,
}) {
  final textTheme = _makoloTextTheme(scheme.onSurface);
  const controlShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.all(Radius.circular(MakoloRadii.control)),
  );

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: surfaces.canvas,
    canvasColor: surfaces.canvas,
    textTheme: textTheme,
    extensions: <ThemeExtension<dynamic>>[surfaces],
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.inner,
          vertical: MakoloSpacing.compact,
        ),
        shape: controlShape,
        textStyle: textTheme.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.inner,
          vertical: MakoloSpacing.compact,
        ),
        shape: controlShape,
        side: BorderSide(color: surfaces.border),
        textStyle: textTheme.labelLarge,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: MakoloSpacing.md),
        shape: controlShape,
        textStyle: textTheme.labelLarge,
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        minimumSize: const Size(48, 48),
        shape: controlShape,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surfaces.low,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: MakoloSpacing.md,
        vertical: MakoloSpacing.compact,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MakoloRadii.control),
        borderSide: BorderSide(color: surfaces.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MakoloRadii.control),
        borderSide: BorderSide(color: surfaces.border),
      ),
      focusedBorder: const OutlineInputBorder(
        borderRadius: BorderRadius.all(Radius.circular(MakoloRadii.control)),
        borderSide: BorderSide(color: MakoloColors.indigo, width: 2),
      ),
      labelStyle: textTheme.bodyMedium,
      hintStyle: textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
    ),
    cardTheme: CardThemeData(
      color: surfaces.surface,
      elevation: MakoloElevation.level0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        side: BorderSide(color: surfaces.border),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: surfaces.low,
      selectedColor: scheme.primaryContainer,
      side: BorderSide(color: surfaces.border),
      shape: const StadiumBorder(),
      labelStyle: textTheme.labelLarge!,
      padding: const EdgeInsets.symmetric(horizontal: MakoloSpacing.sm),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 72,
      elevation: MakoloElevation.level1,
      backgroundColor: surfaces.surface,
      indicatorColor: scheme.primaryContainer,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => textTheme.labelMedium?.copyWith(
          color: states.contains(WidgetState.selected)
              ? scheme.primary
              : scheme.onSurfaceVariant,
        ),
      ),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: surfaces.raised,
      surfaceTintColor: Colors.transparent,
      elevation: MakoloElevation.level2,
      modalElevation: MakoloElevation.level2,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(MakoloRadii.sheet),
        ),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: surfaces.raised,
      surfaceTintColor: Colors.transparent,
      elevation: MakoloElevation.level2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(MakoloRadii.large),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: surfaces.raised,
      contentTextStyle: textTheme.bodyMedium,
      elevation: MakoloElevation.level2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(MakoloRadii.card),
      ),
    ),
    dividerTheme: DividerThemeData(
      color: surfaces.border,
      thickness: 1,
      space: 1,
    ),
  );
}

ThemeData buildMakoloLightTheme() => _buildTheme(
  brightness: Brightness.light,
  scheme: _lightScheme,
  surfaces: MakoloSurfaces.light,
);

ThemeData buildMakoloDarkTheme() => _buildTheme(
  brightness: Brightness.dark,
  scheme: _darkScheme,
  surfaces: MakoloSurfaces.dark,
);

/// Backwards-compatible entry point for A1 callers.
ThemeData buildMakoloTheme() => buildMakoloLightTheme();
