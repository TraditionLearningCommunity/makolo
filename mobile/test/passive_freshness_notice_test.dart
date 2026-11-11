import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/surface_states.dart';

void main() {
  for (final cue in [
    MakoloFreshnessCue.unknown,
    MakoloFreshnessCue.current,
    MakoloFreshnessCue.oldObservation,
    MakoloFreshnessCue.refreshRecommended,
  ]) {
    testWidgets('passive freshness does not interrupt known content: $cue', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                MakoloFreshnessNotice(freshness: cue),
                const Text('Contenu de mon territoire'),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Contenu de mon territoire'), findsOneWidget);
      expect(find.text('Actualisation disponible.'), findsNothing);
      expect(find.text('Informations à actualiser.'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  for (final cue in [
    MakoloFreshnessCue.revalidationRequired,
    MakoloFreshnessCue.expired,
  ]) {
    testWidgets('authority-sensitive freshness remains explicit: $cue', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MakoloFreshnessNotice(freshness: cue),
          ),
        ),
      );
      expect(find.byType(MakoloFreshnessNotice), findsOneWidget);
      expect(
        find.text(
          cue == MakoloFreshnessCue.expired
              ? 'Informations expirées. Vérifiez avant de continuer.'
              : 'Vérification nécessaire avant de continuer.',
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });
  }
}
