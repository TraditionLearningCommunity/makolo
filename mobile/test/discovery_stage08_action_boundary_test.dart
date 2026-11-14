import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_possibility_unit.dart';

import 'support/presentation_harness.dart';

void main() {
  DiscoveryItemPresentation item() => DiscoveryItemPresentation(
    family: 'activity',
    id: 'activity-08',
    candidateKey: 'activity:activity-08',
    title: 'Offre connue hors ligne',
    summary: 'Les faits acquis restent consultables.',
    savedState: 'not_saved',
    capabilities: const {'view', 'save'},
    links: const {},
    wire: const {
      'engagement': {
        'owner': 'commerce',
        'state': 'owner_api',
        'capabilities': ['inspect_offers'],
        'resource': {'kind': 'activity', 'id': 'activity-08'},
        'primary_action': {
          'code': 'inspect_offers',
          'label': 'Voir les offres',
          'destination': {
            'kind': 'native',
            'path': '/commerce/activities/activity-08/checkout',
          },
        },
      },
    },
  );

  testWidgets('cold-start offline N2 keeps facts but never grants owner N3', (
    tester,
  ) async {
    var saved = false;
    var opened = false;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(390, 840),
      child: DiscoveryPossibilityUnit(
        item: item(),
        detailMode: true,
        allowOwnerActions: false,
        onSave: () async => saved = true,
        onOpen: () {},
        onNativeAction: (_) => opened = true,
      ),
    );
    expect(find.text('Offre connue hors ligne'), findsWidgets);
    expect(
      find.textContaining('Une connexion et une vérification'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('discover-primary-n2')), findsNothing);
    final save = tester.widget<IconButton>(
      find.byKey(const Key('discover-save-n2')),
    );
    expect(save.onPressed, isNull);
    expect(saved, isFalse);
    expect(opened, isFalse);
  });

  testWidgets(
    'after owner validation the same N2 may expose real owner action',
    (tester) async {
      String? opened;
      await PresentationHarness.pump(
        tester,
        viewport: const Size(390, 840),
        child: DiscoveryPossibilityUnit(
          item: item(),
          detailMode: true,
          allowOwnerActions: true,
          onOpen: () {},
          onNativeAction: (route) => opened = route,
        ),
      );
      final action = find.byKey(const Key('discover-primary-n2'));
      expect(action, findsOneWidget);
      await tester.ensureVisible(action);
      await tester.tap(action);
      await tester.pump();
      expect(opened, '/commerce/activities/activity-08/checkout');
    },
  );
}
