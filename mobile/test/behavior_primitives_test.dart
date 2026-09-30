import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/behavior_states.dart';
import 'package:makolo_mobile/design/makolo_components.dart';
import 'package:makolo_mobile/design/makolo_patterns.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/design/surface_states.dart';
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

  testWidgets('transient toast uses the Makolo notice foundation', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => showMakoloToast(
                context,
                'Enregistré.',
                kind: MakoloNoticeKind.success,
              ),
              child: const Text('Afficher'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Afficher'));
    await tester.pump();
    expect(find.byType(MakoloNotice), findsOneWidget);
    expect(find.text('Enregistré.'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
  });

  testWidgets('persistent notice stays dismissible with an explicit close', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => showMakoloNotice(
                context,
                'Une modification demande votre attention.',
                kind: MakoloNoticeKind.warning,
                behavior: MakoloNoticeBehavior.persistent,
              ),
              child: const Text('Afficher'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Afficher'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Fermer'), findsOneWidget);
    expect(
      find.text('Une modification demande votre attention.'),
      findsOneWidget,
    );

    await tester.tap(find.byTooltip('Fermer'));
    await tester.pumpAndSettle();
    expect(
      find.text('Une modification demande votre attention.'),
      findsNothing,
    );
  });

  testWidgets('notice meaning never depends on color alone', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: MakoloNotice(
            message: 'Vérifiez cette information.',
            kind: MakoloNoticeKind.warning,
          ),
        ),
      ),
    );

    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    expect(
      find.bySemanticsLabel('Attention. Vérifiez cette information.'),
      findsOneWidget,
    );
  });

  testWidgets('notice motion collapses under Reduce Motion', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: Scaffold(body: MakoloNotice(message: 'Information calme.')),
        ),
      ),
    );

    final animated = tester.widget<AnimatedContainer>(
      find.byType(AnimatedContainer),
    );
    expect(animated.duration, Duration.zero);
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
    expect(
      find.text('Vos données déjà disponibles sont conservées.'),
      findsOneWidget,
    );
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

    await tester.binding.handlePopRoute();
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

  testWidgets('network states remain textual and use semantic notice icons', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: NetworkStateIndicator(
            status: SyncStatus(state: SyncVisualState.offline, pendingCount: 1),
          ),
        ),
      ),
    );

    expect(find.textContaining('Hors connexion'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
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

  testWidgets('refresh preserves usable content', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: MakoloSurfaceStateView(
            state: MakoloSurfacePresentation(
              availability: MakoloAvailabilityCue.content,
              freshness: MakoloFreshnessCue.oldObservation,
              reachability: MakoloReachabilityCue.temporarilyUnavailable,
              refreshing: true,
            ),
            content: Center(child: Text('Contenu local conservé')),
          ),
        ),
      ),
    );

    expect(find.text('Contenu local conservé'), findsOneWidget);
    expect(find.text('Mise à jour…'), findsOneWidget);
    expect(find.textContaining('Données plus anciennes'), findsOneWidget);
    expect(find.textContaining('source distante'), findsOneWidget);
    expect(find.byType(MakoloSkeleton), findsNothing);
  });

  testWidgets('pending differs from confirmed', (tester) async {
    Future<void> pump(MakoloCommitCue commit) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: MakoloSurfaceStateView(
              state: MakoloSurfacePresentation(
                availability: MakoloAvailabilityCue.content,
                commit: commit,
              ),
              content: const SizedBox.expand(),
            ),
          ),
        ),
      );
    }

    await pump(MakoloCommitCue.pending);
    expect(find.text('En attente de synchronisation'), findsOneWidget);
    expect(find.text('Confirmé'), findsNothing);

    await pump(MakoloCommitCue.confirmed);
    expect(find.text('Confirmé'), findsOneWidget);
    expect(find.text('En attente de synchronisation'), findsNothing);
  });

  testWidgets('blocking error stays recoverable', (tester) async {
    var retries = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloSurfaceStateView(
            state: const MakoloSurfacePresentation(
              availability: MakoloAvailabilityCue.content,
              failure: MakoloFailureCue.blocking,
            ),
            content: const Text('should not render'),
            blockingErrorMessage: 'Impossible de continuer.',
            preservedMessage: 'Votre travail local est conservé.',
            onRetry: () => retries += 1,
          ),
        ),
      ),
    );

    expect(find.text('Impossible de continuer.'), findsOneWidget);
    expect(find.text('Votre travail local est conservé.'), findsOneWidget);
    expect(find.text('should not render'), findsNothing);
    await tester.tap(find.text('Réessayer'));
    expect(retries, 1);
  });

  testWidgets('components support large text', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const MediaQuery(
          data: MediaQueryData(textScaler: TextScaler.linear(2)),
          child: Scaffold(
            body: SingleChildScrollView(
              child: MakoloSection(
                title: 'Préparation',
                description: 'Informations utiles avant la prochaine action.',
                child: MakoloCard(
                  semanticLabel: 'Élément de préparation',
                  child: MakoloStatusMetadataAction(
                    title: 'Document',
                    subtitle: 'Disponible sur cet appareil',
                    status: MakoloStatus(
                      label: 'À vérifier',
                      tone: MakoloStatusTone.warning,
                    ),
                    metadata: [
                      MakoloMetadataItem(
                        'Observation ancienne',
                        icon: Icons.schedule_outlined,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(find.text('Préparation'), findsOneWidget);
    expect(find.text('À vérifier'), findsOneWidget);
    expect(find.bySemanticsLabel('Statut : À vérifier'), findsOneWidget);
  });

  testWidgets('patterns expose semantics', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const Scaffold(
          body: SingleChildScrollView(
            padding: EdgeInsets.all(MakoloSpacing.md),
            child: Column(
              children: [
                MakoloAttentionBlock(
                  title: 'Une vérification est nécessaire',
                  body: 'Le contenu reste consultable.',
                ),
                SizedBox(height: MakoloSpacing.lg),
                MakoloTimeline(
                  items: [
                    MakoloTimelineItem(title: 'Préparé', completed: true),
                    MakoloTimelineItem(
                      title: 'Confirmation distante',
                      current: true,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );

    expect(
      find.bySemanticsLabel(
        'Attention. Une vérification est nécessaire. Le contenu reste consultable.',
      ),
      findsOneWidget,
    );
    expect(find.bySemanticsLabel('Terminé. Préparé'), findsOneWidget);
    expect(
      find.bySemanticsLabel('En cours. Confirmation distante'),
      findsOneWidget,
    );
  });

  testWidgets('state transition respects Reduce Motion', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: Scaffold(
            body: MakoloStateTransition(child: Text('État stable')),
          ),
        ),
      ),
    );

    final switcher = tester.widget<AnimatedSwitcher>(
      find.byType(AnimatedSwitcher),
    );
    expect(switcher.duration, Duration.zero);
  });
}
