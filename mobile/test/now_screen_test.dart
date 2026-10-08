import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/presentation/contracts/now_presentation.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

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
    identity: 'now:$id',
    reference: destination,
    humanContext: context,
    meaning: meaning,
    emphasis: primary
        ? NowPresentationEmphasis.primary
        : NowPresentationEmphasis.secondary,
    ownerDestination: destination,
    whyNow: whyNow,
    responseType: capability == null ? null : 'act',
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
          selectionState: 'empty',
          actorAttentionState: 'calm',
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
    expect(find.textContaining('Hors connexion'), findsNothing);
    expect(
      find.textContaining('état actuel ne peut pas être confirmé'),
      findsNothing,
    );
  });

  testWidgets('refresh error preserves known content', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: contentSelection(failure: MakoloFailureCue.recoverable),
      ),
    );

    expect(find.text('Visa Canada'), findsOneWidget);
    expect(find.text('Mise à jour momentanément indisponible.'), findsNothing);
  });

  testWidgets('duplicate context and meaning render only once', (tester) async {
    final duplicate = situation(
      'speech',
      'Vérifier la prochaine étape — Atelier prise de parole',
      'Vérifier la prochaine étape — Atelier prise de parole',
      primary: true,
      whyNow: 'Vérifier la prochaine étape — Atelier prise de parole',
    );
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: NowSelection(
          situations: [duplicate],
          state: const MakoloSurfacePresentation(
            availability: MakoloAvailabilityCue.content,
          ),
        ),
      ),
    );

    expect(
      find.text('Vérifier la prochaine étape — Atelier prise de parole'),
      findsOneWidget,
    );

    await tester.tap(
      find.text('Vérifier la prochaine étape — Atelier prise de parole'),
    );
    await tester.pump();

    expect(
      find.text('Vérifier la prochaine étape — Atelier prise de parole'),
      findsOneWidget,
    );
    expect(find.text('Pourquoi maintenant'), findsNothing);
  });

  testWidgets('uncertain empty does not claim all clear', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: const NowView(
        selection: NowSelection(
          situations: [],
          selectionState: 'partial',
          calmIsCurrent: false,
          state: MakoloSurfacePresentation(
            availability: MakoloAvailabilityCue.empty,
          ),
        ),
      ),
    );

    expect(find.text('Tout est en ordre. ✓'), findsNothing);
    expect(
      find.text('Now n’est pas disponible pour le moment.'),
      findsOneWidget,
    );
  });

  testWidgets('offline calm snapshot does not claim all clear', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: const NowView(
        selection: NowSelection(
          situations: [],
          selectionState: 'empty',
          actorAttentionState: 'calm',
          state: MakoloSurfacePresentation(
            availability: MakoloAvailabilityCue.empty,
            reachability: MakoloReachabilityCue.temporarilyUnavailable,
          ),
        ),
      ),
    );

    expect(find.text('Tout est en ordre. ✓'), findsNothing);
    expect(find.textContaining('Hors connexion'), findsNothing);
    expect(
      find.text('Now n’est pas disponible pour le moment.'),
      findsOneWidget,
    );
  });

  testWidgets('NowScreen consumes the real sync scope', (tester) async {
    final value = StoredProjection(
      kind: 'personal.now',
      schemaVersion: 1,
      payload: const {
        'surface': 'now_me',
        'freshness': {'state': 'fresh'},
        'selection': {'state': 'ready'},
        'actor_attention_state': 'active',
        'items': [
          {
            'id': 'now:visa',
            'human_context': 'Visa Canada',
            'state': 'journey.step.action_required',
            'state_meaning': 'Une action compte maintenant.',
            'handoffs': [
              {'type': 'owner', 'target': 'journey', 'id': 'journey:visa'},
            ],
          },
        ],
        'continuation': null,
        'terminal': {'state': 'ok'},
      },
      receivedAt: DateTime.utc(2026, 10, 7, 12),
      freshUntil: DateTime.utc(2026, 10, 8),
    );

    await PresentationHarness.pump(
      tester,
      child: SyncStatusScope(
        status: const SyncStatus(state: SyncVisualState.offline),
        child: NowScreen(
          repository: _NowStreamRepository(
            projection: Stream.value(value),
            source: Stream.value(OwnerSourceState.unknown),
          ),
          now: () => DateTime.utc(2026, 10, 7, 14),
        ),
      ),
    );

    expect(find.text('Visa Canada'), findsOneWidget);
    expect(find.textContaining('Hors connexion'), findsNothing);
  });

  testWidgets('pending never renders confirmed', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: NowView(
        selection: contentSelection(commit: MakoloCommitCue.pending),
      ),
    );

    expect(find.text('Confirmation en attente'), findsOneWidget);
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

    await tester.tap(find.text('Now'));
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

  test('owner handoff reuses native dossier and conversation routes', () {
    expect(
      NowScreen.ownerPathFor(
        const StructuredDestination(kind: 'dossier', id: 'dossier:1'),
      ),
      '/dossiers/dossier%3A1',
    );
    expect(
      NowScreen.ownerPathFor(
        const StructuredDestination(kind: 'conversation', id: 'thread:1'),
      ),
      '/conversations/thread%3A1',
    );
  });

  test('owner deep link accepts the opaque owner-prefixed id', () {
    expect(
      NowScreen.ownerPathFor(
        StructuredDestination(kind: 'journey', id: 'journey:visa-canada'),
      ),
      '/journeys/journey%3Avisa-canada',
    );
  });
}

class _NowStreamRepository extends PersonalRepository {
  _NowStreamRepository({required this.projection, required this.source})
    : super(_NeverUsedStore());

  final Stream<StoredProjection?> projection;
  final Stream<OwnerSourceState> source;

  @override
  Stream<StoredProjection?> watchNow() => projection;

  @override
  Stream<OwnerSourceState> watchNowSource() => source;
}

class _NeverUsedStore implements ProfileStore {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
