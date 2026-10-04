import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

import 'support/presentation_harness.dart';

NowSituationPresentation situation(
  String id,
  String context,
  String meaning, {
  bool primary = false,
  String? whyNow,
  String? capability,
}) {
  final destination = StructuredDestination(kind: 'journey', id: id);
  return NowSituationPresentation(
    reference: destination,
    humanContext: context,
    meaning: meaning,
    emphasis: primary
        ? NowPresentationEmphasis.primary
        : NowPresentationEmphasis.secondary,
    ownerDestination: destination,
    whyNow: whyNow,
    responseLabel: capability == null ? null : 'Ouvrir',
    responseCapability: capability,
  );
}

NowSelection contentSelection({
  MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
  MakoloCommitCue commit = MakoloCommitCue.none,
  MakoloFailureCue failure = MakoloFailureCue.none,
}) {
  return NowSelection(
    situations: [
      situation(
        'visa',
        'Visa Canada',
        'Votre certificat doit être transmis aujourd’hui.',
        primary: true,
        whyNow: 'La fenêtre ferme aujourd’hui.',
        capability: 'open_detail',
      ),
      situation('trip', 'Départ vers Kolwezi', 'Le départ est prévu à 14:00.'),
    ],
    state: MakoloSurfacePresentation(
      availability: MakoloAvailabilityCue.content,
      reachability: reachability,
      commit: commit,
      failure: failure,
    ),
  );
}

void main() {
  testWidgets(
    'G01 compact keeps one dominant consequence and quieter secondary',
    (tester) async {
      await PresentationHarness.pump(
        tester,
        child: NowView(selection: contentSelection()),
      );

      expect(
        find.text('Votre certificat doit être transmis aujourd’hui.'),
        findsOneWidget,
      );
      expect(find.text('Aussi maintenant'), findsOneWidget);
      expect(find.text('Départ vers Kolwezi'), findsOneWidget);
      expect(find.text('Ouvrir'), findsNothing);
    },
  );

  testWidgets('known calm is a successful quiet ending', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: const NowView(
        selection: NowSelection(
          situations: [],
          state: MakoloSurfacePresentation(
            availability: MakoloAvailabilityCue.empty,
          ),
        ),
      ),
    );

    expect(find.text('Tout est en ordre. ✓'), findsOneWidget);
  });

  testWidgets('content plus offline remains visually Now', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: contentSelection(
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
        ),
      ),
    );

    expect(find.text('Visa Canada'), findsOneWidget);
    expect(find.textContaining('source distante'), findsOneWidget);
  });

  testWidgets('refresh error preserves known content', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: contentSelection(failure: MakoloFailureCue.recoverable),
      ),
    );

    expect(find.text('Visa Canada'), findsOneWidget);
    expect(find.textContaining('mise à jour'), findsOneWidget);
  });

  testWidgets('pending never renders confirmed', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: contentSelection(commit: MakoloCommitCue.pending),
      ),
    );

    expect(find.text('En attente de synchronisation'), findsOneWidget);
    expect(find.text('Confirmé'), findsNothing);
  });

  testWidgets('compact N2 replaces field and back restores it', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: NowView(selection: contentSelection()),
    );

    await tester.tap(find.text('Visa Canada'));
    await tester.pump();

    expect(find.text('Pourquoi maintenant'), findsOneWidget);
    expect(find.text('Aussi maintenant'), findsNothing);

    await tester.tap(find.text('Maintenant'));
    await tester.pump();

    expect(find.text('Aussi maintenant'), findsOneWidget);
  });

  testWidgets('G02 wide opens shared split only after a real selection', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1440, 900),
      child: NowView(selection: contentSelection()),
    );

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsNothing);

    await tester.tap(find.text('Visa Canada'));
    await tester.pump();

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
    expect(find.text('Pourquoi maintenant'), findsOneWidget);
    expect(find.text('Aussi maintenant'), findsOneWidget);
  });

  testWidgets('shared Now breakpoint opens split at 960 but not below', (
    tester,
  ) async {
    for (final width in [920.0, 960.0, 1000.0]) {
      await PresentationHarness.pump(
        tester,
        viewport: Size(width, 800),
        child: NowView(
          key: ValueKey('now-breakpoint-$width'),
          selection: contentSelection(),
        ),
      );

      await tester.tap(find.text('Visa Canada').first);
      await tester.pump();

      final expected = width >= 960 ? findsOneWidget : findsNothing;
      expect(find.byKey(const Key('makolo-adaptive-split-row')), expected);
    }
  });

  testWidgets('critical text scale keeps content reachable', (tester) async {
    await PresentationHarness.pump(
      tester,
      textScale: 1.6,
      child: NowView(selection: contentSelection()),
    );

    expect(
      find.text('Votre certificat doit être transmis aujourd’hui.'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('owner CTA appears only when an executable handoff exists', (
    tester,
  ) async {
    StructuredDestination? opened;

    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: contentSelection(),
        onOpenOwner: (value) => opened = value,
      ),
    );

    expect(find.text('Ouvrir'), findsOneWidget);
    await tester.tap(find.text('Ouvrir'));
    await tester.pump();

    expect(opened?.id, 'visa');
  });
}
