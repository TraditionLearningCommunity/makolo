import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/surface_states.dart';

import 'support/presentation_harness.dart';

void main() {
  testWidgets('content plus offline keeps the known content visible', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: const MakoloSurfaceStateView(
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
        ),
        content: Center(child: Text('État connu')),
      ),
    );

    expect(find.text('État connu'), findsOneWidget);
    expect(find.textContaining('source distante'), findsNothing);
    expect(find.byType(MakoloNotice), findsNothing);
  });

  testWidgets('refresh error preserves content and adds local support', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: const MakoloSurfaceStateView(
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          failure: MakoloFailureCue.recoverable,
          refreshing: true,
        ),
        content: Center(child: Text('Continuité conservée')),
        recoverableErrorMessage: 'La mise à jour a échoué.',
      ),
    );

    expect(find.text('Continuité conservée'), findsOneWidget);
    expect(find.text('La mise à jour a échoué.'), findsNothing);
    expect(find.text('Mise à jour…'), findsNothing);
    expect(find.byType(MakoloNotice), findsNothing);
    expect(find.byType(MakoloSkeleton), findsNothing);
  });

  testWidgets('pending content never renders false confirmation', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: const MakoloSurfaceStateView(
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          commit: MakoloCommitCue.pending,
        ),
        content: Center(child: Text('Brouillon')),
      ),
    );

    expect(find.text('Brouillon'), findsOneWidget);
    expect(find.text('En attente de synchronisation'), findsOneWidget);
    expect(find.text('Confirmé'), findsNothing);
  });
}
