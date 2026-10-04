import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/discovery/discovery_mature_view.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/platform/maps/map_runtime_config.dart';

import 'support/presentation_harness.dart';

DiscoveryItemPresentation item(
  String id,
  String title, {
  bool mappable = false,
  String? imageUrl,
  String? routeLabel,
}) {
  return DiscoveryItemPresentation(
    family: 'activity',
    id: id,
    candidateKey: 'activity:$id',
    occurrenceId: mappable ? 'occ-$id' : null,
    representationKind: routeLabel == null ? 'event' : 'route',
    routeLabel: routeLabel,
    title: title,
    summary: 'Résumé de $title',
    imageUrl: imageUrl,
    eyebrow: 'À explorer',
    owner: 'Espace test',
    place: mappable ? 'Lubumbashi' : 'À distance',
    timing: '2026-10-05 09:00',
    availability: 'available',
    price: 'Gratuit',
    latitude: mappable ? -11.66 + id.length / 100 : null,
    longitude: mappable ? 27.48 + id.length / 100 : null,
    distanceKm: mappable ? 3 : null,
    savedState: 'not_saved',
    capabilities: const {'view', 'save'},
    links: const {'detail': '/api/v1/discovery/items/activity/test/'},
  );
}

DiscoveryFieldSelection selection({
  List<DiscoveryItemPresentation>? items,
  Set<DiscoveryFieldState> states = const {},
  MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
  MakoloFailureCue failure = MakoloFailureCue.none,
}) {
  final values =
      items ??
      [
        item(
          'media',
          'Formation Data Science',
          imageUrl: 'fixture://discover/data-science',
          mappable: true,
        ),
        item(
          'route',
          'Voyage vers Kolwezi',
          routeLabel: 'Lubumbashi → Kolwezi',
          mappable: true,
        ),
        item('remote', 'Accompagnement à distance'),
      ];
  return DiscoveryFieldSelection(
    collection: DiscoveryCollectionPresentation(
      items: values,
      count: values.length,
      page: 1,
      pageSize: 24,
      hasNext: false,
    ),
    surface: MakoloSurfacePresentation(
      availability: values.isEmpty
          ? MakoloAvailabilityCue.empty
          : MakoloAvailabilityCue.content,
      reachability: reachability,
      failure: failure,
    ),
    states: states,
  );
}

void main() {
  testWidgets('G03 compact renders a natural possibility field', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(states: const {DiscoveryFieldState.endOfField}),
        onOpen: (_) {},
      ),
    );

    expect(find.byKey(const Key('discover-compact-field')), findsOneWidget);
    expect(find.byKey(const Key('discover-wide-grid')), findsNothing);
    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.text('Lubumbashi → Kolwezi'), findsOneWidget);
    expect(find.text('Accompagnement à distance'), findsOneWidget);
    expect(find.text('S’inscrire'), findsNothing);
    expect(find.textContaining('contenu de remplissage'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('G04 wide uses the shared adaptive grid', (tester) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1440, 900),
      child: DiscoveryExplorationView(selection: selection(), onOpen: (_) {}),
    );

    expect(find.byKey(const Key('discover-wide-grid')), findsOneWidget);
    expect(find.byKey(const Key('discover-compact-field')), findsNothing);
    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.text('Accompagnement à distance'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('wide N2 keeps the field and opens shared focus depth', (
    tester,
  ) async {
    DiscoveryItemPresentation? opened;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1200, 800),
      child: DiscoveryExplorationView(
        selection: selection(),
        onOpen: (value) => opened = value,
      ),
    );

    await tester.tap(find.text('Formation Data Science').first);
    await tester.pump();

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
    expect(find.byKey(const Key('discover-focus-depth')), findsOneWidget);
    expect(find.text('Accompagnement à distance'), findsOneWidget);
    expect(find.text('Ouvrir le détail'), findsOneWidget);

    await tester.tap(find.text('Ouvrir le détail'));
    await tester.pump();
    expect(opened?.id, 'media');

    await tester.tap(find.text('Découvrir').last);
    await tester.pump();
    expect(find.byKey(const Key('discover-focus-depth')), findsNothing);
    expect(find.text('Formation Data Science'), findsOneWidget);
  });

  testWidgets('G05 uses the shared 1040 spatial threshold', (tester) async {
    for (final width in [1000.0, 1040.0, 1080.0]) {
      await PresentationHarness.pump(
        tester,
        viewport: Size(width, 800),
        child: DiscoverySpatialView(
          selection: selection(),
          mapConfig: const MakoloMapsConfig(enabled: false, style: null),
          onOpen: (_) {},
        ),
      );

      final expected = width >= 1040 ? findsOneWidget : findsNothing;
      expect(find.byKey(const Key('makolo-adaptive-split-row')), expected);
    }
  });

  testWidgets('G05 spatial split projects the same field and selection', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1200, 800),
      child: DiscoverySpatialView(
        selection: selection(),
        mapConfig: const MakoloMapsConfig(enabled: false, style: null),
        onOpen: (_) {},
      ),
    );

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
    expect(find.byKey(const Key('discover-spatial-pane')), findsOneWidget);
    expect(find.byKey(const Key('discover-spatial-stack')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('discover-map-activity:media')),
      findsOneWidget,
    );
    expect(find.text('Voir sur la carte'), findsNWidgets(2));
    expect(find.text('Accompagnement à distance'), findsOneWidget);

    final secondMapAction = find.byKey(
      const ValueKey('discover-map-action-activity:route'),
    );
    await tester.ensureVisible(secondMapAction);
    await tester.pump();
    await tester.tap(secondMapAction);
    await tester.pump();

    expect(
      find.byKey(const ValueKey('discover-map-activity:route')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('NO_MATCH keeps criteria choice explicit', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          items: const [],
          states: const {DiscoveryFieldState.noMatch},
        ),
        onOpen: (_) {},
        onResetCriteria: () {},
      ),
    );

    expect(
      find.text('Aucune possibilité ne correspond à ces critères.'),
      findsOneWidget,
    );
    expect(find.text('Modifier mes critères'), findsOneWidget);
    expect(find.textContaining('hors connexion'), findsNothing);
  });

  testWidgets('offline without snapshot is not rendered as no match', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          items: const [],
          states: const {DiscoveryFieldState.offlineNoSnapshot},
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
        ),
        onOpen: (_) {},
        onRetry: () {},
      ),
    );

    expect(
      find.text(
        'Impossible de charger de nouvelles possibilités hors connexion.',
      ),
      findsOneWidget,
    );
    expect(
      find.text('Aucune possibilité ne correspond à ces critères.'),
      findsNothing,
    );
  });

  testWidgets('offline with snapshot keeps acquired possibilities visible', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          states: const {DiscoveryFieldState.offlineWithSnapshot},
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
          failure: MakoloFailureCue.recoverable,
        ),
        onOpen: (_) {},
      ),
    );

    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.textContaining('source distante'), findsOneWidget);
    expect(find.textContaining('mise à jour'), findsOneWidget);
  });

  testWidgets('critical text scale keeps compact field reachable', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      textScale: 1.6,
      child: DiscoveryExplorationView(selection: selection(), onOpen: (_) {}),
    );

    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.byKey(const Key('discover-compact-field')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
