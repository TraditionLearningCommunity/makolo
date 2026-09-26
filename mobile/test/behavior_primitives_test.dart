import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

void main() {
  testWidgets('success feedback distinguishes local pending and confirmed', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: Column(
            children: [
              SuccessFeedback(kind: SuccessFeedbackKind.savedOnDevice),
              SuccessFeedback(kind: SuccessFeedbackKind.pendingSync),
              SuccessFeedback(kind: SuccessFeedbackKind.confirmed),
            ],
          ),
        ),
      ),
    );

    expect(find.text('Enregistré sur cet appareil'), findsOneWidget);
    expect(find.text('En attente de synchronisation'), findsOneWidget);
    expect(find.text('Confirmé'), findsOneWidget);
  });

  testWidgets('blocking errors remain persistent and actionable', (
    tester,
  ) async {
    var retries = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloErrorState(
            message: 'Impossible de mettre à jour pour le moment.',
            preservedMessage: 'Vos données déjà disponibles sont conservées.',
            onRetry: () => retries += 1,
          ),
        ),
      ),
    );

    expect(find.byType(SnackBar), findsNothing);
    expect(find.text('Vos données déjà disponibles sont conservées.'), findsOneWidget);
    await tester.tap(find.text('Réessayer'));
    expect(retries, 1);
  });

  testWidgets('bottom sheet foundation opens and closes with back', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => showMakoloBottomSheet<void>(
                context,
                builder: (_) => const SizedBox(
                  height: 240,
                  child: Center(child: Text('Actions secondaires')),
                ),
              ),
              child: const Text('Ouvrir'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Ouvrir'));
    await tester.pumpAndSettle();
    expect(find.text('Actions secondaires'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('Actions secondaires'), findsNothing);
  });

  testWidgets('permission explainer supports denied state without OS prompt', (
    tester,
  ) async {
    var continued = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: PermissionExplainer(
            title: 'Afficher ce qui se trouve autour de vous',
            message: 'Votre position sera utilisée pour cette expérience.',
            actionLabel: 'Continuer',
            denied: true,
            onContinue: () => continued = true,
          ),
        ),
      ),
    );

    expect(find.textContaining('autorisation est refusée'), findsOneWidget);
    await tester.tap(find.text('Continuer'));
    expect(continued, isTrue);
  });

  testWidgets('network states remain textual and not color-only', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: NetworkStateIndicator(
            status: SyncStatus(
              state: SyncVisualState.offline,
              pendingCount: 1,
            ),
          ),
        ),
      ),
    );

    expect(find.text('Hors connexion'), findsOneWidget);
    expect(find.byIcon(Icons.cloud_off_outlined), findsOneWidget);
  });

  testWidgets('skeleton respects Reduce Motion and large text context', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const MediaQuery(
          data: MediaQueryData(
            disableAnimations: true,
            textScaler: TextScaler.linear(2),
          ),
          child: Scaffold(body: MakoloSkeleton(lines: 3)),
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(find.bySemanticsLabel('Chargement du contenu'), findsOneWidget);
  });
}
