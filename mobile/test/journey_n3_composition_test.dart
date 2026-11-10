import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_detail_screen.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/preparation/preparation_repository.dart';

void main() {
  testWidgets(
    'N3 composes goal, date, hour, city and day without repeated cards',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-ui');
      const journeyId = 'journey-visual';
      await store.putProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: journeyId,
        schemaVersion: 1,
        payload: const {
          'identity': {'workflow': 'registration'},
          'representation': {'title': "Recevoir un badge d'accès conférence"},
          'state': {'code': 'in_progress', 'label': 'En cours'},
          'readiness': {
            'state': 'action_required',
            'actor_interventions': [
              {
                'key': 'summary-only',
                'summary': "Recevoir un badge d'accès conférence",
              },
            ],
            'ready': [],
            'waiting': [],
            'blockers': [],
          },
          'steps': [],
          'forms': [],
          'requirements': [],
          'occurrence': {
            'id': 'occurrence-1',
            'label': 'Conférence',
            'state': 'scheduled',
            'timing': {
              'start_date': '2026-12-11',
              'start_time': '09:00:00',
              'timezone': 'Africa/Lubumbashi',
            },
            'place': {'name': 'Lubumbashi', 'locality': 'Lubumbashi'},
          },
          'resources': {
            'link': '/api/v1/preparation/journeys/journey-visual/resources/',
          },
          'capabilities': [],
        },
      );
      await store.putProjection(
        kind: PreparationResourcesRepository.projectionKind,
        resourceKey: journeyId,
        schemaVersion: 1,
        payload: const {
          'items': [
            {
              'id': 'res-pdf',
              'title': 'Guide de préparation',
              'kind': 'file',
              'mime_type': 'application/pdf',
            },
            {
              'id': 'res-photo',
              'title': 'Image documentaire',
              'kind': 'file',
              'mime_type': 'image/jpeg',
            },
          ],
        },
      );
      final journeys = JourneyRepository(
        database: database,
        store: store,
        profileId: 'profile-ui',
      );
      final resources = PreparationResourcesRepository(
        database: database,
        store: store,
        profileId: 'profile-ui',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: JourneyDetailScreen(
            journeyId: journeyId,
            repository: journeys,
            resourcesRepository: resources,
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

      expect(find.text("Recevoir un badge d'accès conférence"), findsOneWidget);
      expect(find.text('09h00'), findsOneWidget);
      expect(find.text('Lubumbashi'), findsOneWidget);
      expect(find.byKey(const Key('journey-relative-day')), findsOneWidget);
      expect(find.text('Africa/Lubumbashi'), findsNothing);
      expect(find.text('À retenir'), findsNothing);
      expect(find.text('De votre côté'), findsNothing);
      await tester.scrollUntilVisible(
        find.text('Guide de préparation'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Guide de préparation'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
