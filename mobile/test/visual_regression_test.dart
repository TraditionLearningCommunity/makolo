import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/design/makolo_mark.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  Future<void> pumpGolden(
    WidgetTester tester, {
    required ThemeData theme,
    required Widget child,
    double textScale = 1,
  }) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: theme,
        home: MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
          child: RepaintBoundary(child: child),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('visual system light reference', (tester) async {
    await pumpGolden(
      tester,
      theme: buildMakoloLightTheme(),
      child: const _VisualSystemFixture(),
    );

    await expectLater(
      find.byType(_VisualSystemFixture),
      matchesGoldenFile('goldens/visual-system-light.png'),
    );
  });

  testWidgets('visual system dark reference', (tester) async {
    await pumpGolden(
      tester,
      theme: buildMakoloDarkTheme(),
      child: const _VisualSystemFixture(),
    );

    await expectLater(
      find.byType(_VisualSystemFixture),
      matchesGoldenFile('goldens/visual-system-dark.png'),
    );
  });

  testWidgets('all-clear remains calm with elevated text scaling', (
    tester,
  ) async {
    await pumpGolden(
      tester,
      theme: buildMakoloLightTheme(),
      textScale: 1.6,
      child: const Scaffold(
        body: SafeArea(
          child: MakoloEmptyState(
            title: 'Tout est en ordre. ✓',
            body: 'Rien ne demande votre attention pour le moment.',
          ),
        ),
      ),
    );

    await expectLater(
      find.byType(MakoloEmptyState),
      matchesGoldenFile('goldens/all-clear-large-text.png'),
    );
  });
}

class _VisualSystemFixture extends StatelessWidget {
  const _VisualSystemFixture();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          children: [
            const MakoloMark(size: 44),
            const SizedBox(height: MakoloSpacing.lg),
            Text(
              'Makolo',
              style: Theme.of(context).textTheme.headlineLarge,
            ),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Calme quand tout va bien, précis quand quelque chose compte.',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: MakoloSpacing.xl),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(MakoloSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Une prochaine étape',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      'Le contenant reste léger et l’action reste claire.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    const Wrap(
                      spacing: MakoloSpacing.sm,
                      children: [
                        Chip(label: Text('Contexte')),
                        Chip(label: Text('Prêt')),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: MakoloSpacing.lg),
            const MakoloNotice(
              message: 'Ce qui était déjà disponible reste accessible.',
              kind: MakoloNoticeKind.info,
            ),
            const SizedBox(height: MakoloSpacing.lg),
            FilledButton(
              onPressed: null,
              child: const Text('Action principale'),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            OutlinedButton(
              onPressed: null,
              child: const Text('Action secondaire'),
            ),
          ],
        ),
      ),
    );
  }
}
