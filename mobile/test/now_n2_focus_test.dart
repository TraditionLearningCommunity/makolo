import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';

import 'support/presentation_harness.dart';

NowSelection _selection(NowSituationPresentation item) => NowSelection(
  situations: [item],
  state: const MakoloSurfacePresentation(
    availability: MakoloAvailabilityCue.content,
  ),
);

const _reference = StructuredDestination(kind: 'now', id: 'n2-test');

void main() {
  testWidgets('Now N2 preserves owner subject delta and waiting exit', (
    tester,
  ) async {
    const item = NowSituationPresentation(
      identity: 'n2-semantic-wait',
      reference: _reference,
      humanContext: 'Démarche',
      meaning: 'Une réponse est attendue.',
      subject: 'Réservation',
      delta: 'Le statut a changé.',
      exitCondition: 'La réservation est confirmée.',
      responseType: 'wait',
      emphasis: NowPresentationEmphasis.primary,
    );
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: _selection(item),
        initialSelectedKey: item.identity,
      ),
    );
    await tester.pump();
    expect(find.text('Réservation'), findsOneWidget);
    expect(find.text('Le statut a changé.'), findsOneWidget);
    expect(find.text('La réservation est confirmée.'), findsOneWidget);
  });

  testWidgets('Now S1 N2 leads with impact and keeps server meaning', (
    tester,
  ) async {
    const item = NowSituationPresentation(
      identity: 'n2-meaning',
      reference: _reference,
      humanContext: 'Inscription',
      meaning: 'Un justificatif est demandé.',
      whyNow: 'La date limite approche.',
      consequence: 'La suite dépend du document.',
      responseType: 'understand',
      emphasis: NowPresentationEmphasis.primary,
    );
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: _selection(item),
        initialSelectedKey: item.identity,
      ),
    );
    await tester.pump();
    expect(find.text('Ce que ça change'), findsOneWidget);
    expect(find.text('La suite dépend du document.'), findsOneWidget);
    expect(find.text('Pourquoi maintenant'), findsOneWidget);
    expect(find.text('Inscription'), findsWidgets);
    expect(find.text('Partager'), findsNothing);
  });

  testWidgets('Now S4 N2 shows a true waiting turn without fake action', (
    tester,
  ) async {
    const item = NowSituationPresentation(
      identity: 'n2-waiting',
      reference: _reference,
      humanContext: 'Demande envoyée',
      meaning: 'Une réponse est attendue.',
      responseType: 'wait',
      turnLabel: 'Le consulat doit répondre.',
      horizon: 'Réponse attendue en novembre.',
      emphasis: NowPresentationEmphasis.primary,
    );
    expect(topologyFor(item), NowTopology.waiting);
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: _selection(item),
        initialSelectedKey: item.identity,
      ),
    );
    await tester.pump();
    expect(find.text('Le consulat doit répondre.'), findsOneWidget);
    expect(find.text('Réponse attendue en novembre.'), findsOneWidget);
    expect(find.text('Accepter'), findsNothing);
  });

  testWidgets('Now S5 N2 exposes the actual relation and two members', (
    tester,
  ) async {
    const item = NowSituationPresentation(
      identity: 'n2-conflict',
      reference: _reference,
      humanContext: 'Deux rendez-vous',
      meaning: 'Les horaires sont incompatibles.',
      whyNow: 'Ils ont lieu en même temps.',
      consequence: 'Une présence simultanée est impossible.',
      responseType: 'decide',
      emphasis: NowPresentationEmphasis.primary,
      relationMembers: [
        NowRelationMemberPresentation(id: 'a', label: 'Rendez-vous A'),
        NowRelationMemberPresentation(id: 'b', label: 'Rendez-vous B'),
      ],
      relations: [
        NowRelationPresentation(
          kind: 'conflict',
          memberIds: ['a', 'b'],
          summary: 'Même horaire.',
        ),
      ],
    );
    expect(topologyFor(item), NowTopology.composition);
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1440, 900),
      child: NowView(
        selection: _selection(item),
        initialSelectedKey: item.identity,
      ),
    );
    await tester.pump();
    // Wide layout displays N1 and N2 together; check the focused pane.
    final focus = find.byKey(const ValueKey('now-n2-scroll-n2-conflict'));
    expect(
      find.descendant(of: focus, matching: find.text('Rendez-vous A')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: focus, matching: find.text('Rendez-vous B')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: focus, matching: find.text('Même horaire.')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
  });
}
