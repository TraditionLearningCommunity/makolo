import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/makolo_patterns.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';

void main() {
  testWidgets('action feedback shows processing, failure and confirmation', (
    tester,
  ) async {
    Future<void> render(MakoloActionPhase phase) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 120,
                child: MakoloRoundedActionSlot(
                  phase: phase,
                  active: phase == MakoloActionPhase.confirmed,
                  child: MakoloActionFeedback(
                    phase: phase,
                    child: const Icon(Icons.bookmark_rounded),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    await render(MakoloActionPhase.available);
    expect(find.byIcon(Icons.bookmark_rounded), findsOneWidget);

    await render(MakoloActionPhase.processing);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.byIcon(Icons.bookmark_rounded), findsNothing);

    await render(MakoloActionPhase.failed);
    expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);

    await render(MakoloActionPhase.confirmed);
    expect(find.byIcon(Icons.bookmark_rounded), findsOneWidget);
  });

  testWidgets('action transition respects reduced motion', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: Scaffold(
            body: MakoloRoundedActionSlot(
              phase: MakoloActionPhase.processing,
              child: MakoloActionFeedback(
                phase: MakoloActionPhase.processing,
                child: Icon(Icons.bookmark_border_rounded),
              ),
            ),
          ),
        ),
      ),
    );
    final animations = tester.widgetList<AnimatedContainer>(
      find.byType(AnimatedContainer),
    );
    expect(animations, isNotEmpty);
    expect(animations.first.duration, Duration.zero);
    expect(
      tester.widget<AnimatedSwitcher>(find.byType(AnimatedSwitcher)).duration,
      Duration.zero,
    );
  });

  testWidgets('skeletons reflect the two different feed surfaces', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: const Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: [
                MakoloCardSkeleton(
                  kind: MakoloCardSkeletonKind.discover,
                  count: 1,
                ),
                MakoloCardSkeleton(
                  kind: MakoloCardSkeletonKind.ongoing,
                  count: 1,
                ),
              ],
            ),
          ),
        ),
      ),
    );
    expect(find.byType(MakoloCardSkeleton), findsNWidgets(2));
    expect(
      find.bySemanticsLabel('Chargement des possibilités'),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel('Chargement des éléments en cours'),
      findsOneWidget,
    );
  });

  testWidgets('quick preview opens only on deliberate request', (tester) async {
    var opened = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              child: const Text('Aperçu'),
              onPressed: () => showMakoloQuickPreview(
                context,
                title: 'Porteur public',
                eyebrow: 'Espace',
                facts: const ['Lubumbashi'],
                onOpen: () => opened++,
                actionLabel: 'Ouvrir l’Espace',
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('Porteur public'), findsNothing);
    await tester.tap(find.text('Aperçu'));
    await tester.pumpAndSettle();
    expect(find.text('Porteur public'), findsOneWidget);
    expect(find.text('Lubumbashi'), findsOneWidget);
    expect(opened, 0);

    await tester.tap(find.text('Ouvrir l’Espace'));
    await tester.pumpAndSettle();
    expect(opened, 1);
    expect(find.text('Porteur public'), findsNothing);
  });
}
