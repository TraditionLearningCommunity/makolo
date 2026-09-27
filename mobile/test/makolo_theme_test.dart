import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  test('light theme uses explicit Makolo colors and surfaces', () {
    final theme = buildMakoloLightTheme();
    final surfaces = theme.extension<MakoloSurfaces>();

    expect(theme.brightness, Brightness.light);
    expect(theme.colorScheme.primary, MakoloColors.indigo);
    expect(theme.scaffoldBackgroundColor, MakoloColors.warm);
    expect(theme.colorScheme.surface, MakoloColors.lightSurface);
    expect(theme.colorScheme.onSurface, MakoloColors.ink);
    expect(surfaces, MakoloSurfaces.light);
  });

  test('dark theme keeps Ink canvas and ordered dark surfaces', () {
    final theme = buildMakoloDarkTheme();
    final surfaces = theme.extension<MakoloSurfaces>()!;

    expect(theme.brightness, Brightness.dark);
    expect(theme.scaffoldBackgroundColor, MakoloColors.ink);
    expect(surfaces.canvas, MakoloColors.ink);
    expect(surfaces.low, MakoloColors.darkSurfaceLow);
    expect(surfaces.surface, MakoloColors.darkSurface);
    expect(surfaces.raised, MakoloColors.darkSurfaceRaised);
    expect(theme.colorScheme.primary, MakoloColors.indigo);
  });

  test('visual charter spacing, radius and motion tokens are centralized', () {
    expect(
      [
        MakoloSpacing.micro,
        MakoloSpacing.sm,
        MakoloSpacing.compact,
        MakoloSpacing.md,
        MakoloSpacing.inner,
        MakoloSpacing.lg,
        MakoloSpacing.xl,
        MakoloSpacing.strong,
        MakoloSpacing.structure,
        MakoloSpacing.exceptional,
      ],
      [4, 8, 12, 16, 20, 24, 32, 40, 48, 64],
    );

    expect(MakoloRadii.control, 12);
    expect(MakoloRadii.card, 16);
    expect(MakoloRadii.large, 24);
    expect(MakoloRadii.sheet, 28);

    expect(MakoloMotion.instant, const Duration(milliseconds: 120));
    expect(MakoloMotion.short, const Duration(milliseconds: 160));
    expect(MakoloMotion.medium, const Duration(milliseconds: 240));
    expect(MakoloMotion.structural, const Duration(milliseconds: 320));
  });

  testWidgets('Reduce Motion collapses Makolo motion durations', (
    tester,
  ) async {
    late Duration duration;
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: Builder(
            builder: (context) {
              duration = MakoloMotion.effective(
                context,
                MakoloMotion.structural,
              );
              return const SizedBox.shrink();
            },
          ),
        ),
      ),
    );

    expect(duration, Duration.zero);
  });

  test(
    'canonical typography scale is defined without pretending fonts exist',
    () {
      final textTheme = buildMakoloLightTheme().textTheme;

      expect(textTheme.displayLarge?.fontSize, 32);
      expect(textTheme.displayLarge?.fontWeight, FontWeight.w800);
      expect(textTheme.headlineLarge?.fontSize, 28);
      expect(textTheme.headlineMedium?.fontSize, 24);
      expect(textTheme.headlineSmall?.fontSize, 20);
      expect(textTheme.titleLarge?.fontSize, 17);
      expect(textTheme.bodyLarge?.fontSize, 16);
      expect(textTheme.bodyMedium?.fontSize, 14);
      expect(textTheme.labelLarge?.fontSize, 13);
      expect(textTheme.bodySmall?.fontSize, 12);
      expect(textTheme.labelMedium?.fontSize, 11);

      expect(textTheme.displayLarge?.fontFamily, isNull);
      expect(textTheme.bodyLarge?.fontFamily, isNull);
    },
  );

  test('shared component themes enforce charter geometry', () {
    final theme = buildMakoloLightTheme();

    expect(theme.navigationBarTheme.height, 72);
    expect(theme.cardTheme.elevation, MakoloElevation.level0);
    expect(theme.bottomSheetTheme.elevation, MakoloElevation.level2);
    expect(theme.dialogTheme.elevation, MakoloElevation.level2);
    expect(theme.snackBarTheme.behavior, SnackBarBehavior.floating);
  });
}
