import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_detail_screen.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';

void main() {
  testWidgets(
    'N3 cover shows the full schedule and only distinct arrival notes',
    (tester) async {
      tester.view.physicalSize = const Size(340, 760);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-cover');
      await store.putProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'journey-cover',
        schemaVersion: 1,
        payload: const {
          'identity': {'workflow': 'registration'},
          'representation': {'title': 'Conférence à Kampala'},
          'state': {'code': 'in_progress', 'label': 'En cours'},
          'readiness': {
            'state': 'ready',
            'ready': [],
            'actor_interventions': [],
            'waiting': [],
            'blockers': [],
          },
          'forms': [],
          'requirements': [],
          'steps': [],
          'capabilities': [],
          'occurrence': {
            'id': 'occurrence-kampala',
            'timing': {
              'start_date': '2026-12-12',
              'start_time': '15:00:00',
              'end_date': '2026-12-12',
              'end_time': '18:00:00',
              'timezone': 'Africa/Kampala',
            },
            'place': {
              'name': 'Kampala',
              'locality': 'Kampala',
              'address': 'Centre-ville, Kampala',
              'instructions': 'Présentez-vous à la porte B.',
            },
          },
        },
      );
      final journeys = JourneyRepository(
        database: database,
        store: store,
        profileId: 'profile-cover',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: JourneyDetailScreen(
            journeyId: 'journey-cover',
            repository: journeys,
            onOpenForm: (_) {},
            onOpenRequirement: (_) {},
            onOpenResources: (_) {},
            onOpenActivity: (_) {},
            onOpenOccurrence: (_) {},
            onOpenAccess: (_) {},
            onOpenDayOf: (_) {},
            onOpenLive: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.track_changes_rounded), findsOneWidget);
      expect(find.text('15h–18h'), findsOneWidget);
      expect(find.text('Kampala'), findsOneWidget);
      expect(find.text('Centre-ville'), findsOneWidget);
      expect(find.text('Fin prévue'), findsNothing);
      expect(find.text('Adresse'), findsNothing);
      expect(find.text('Sur place'), findsOneWidget);
      expect(find.text('Présentez-vous à la porte B.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
