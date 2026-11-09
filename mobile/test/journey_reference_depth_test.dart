import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_detail_screen.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/preparation/preparation_repository.dart';
import 'package:makolo_mobile/features/journey/journey_selector.dart';
import 'package:makolo_mobile/sync/freshness.dart';

void main() {
  test(
    'Journey source is the canonical keyed owner-backed definition',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = JourneyRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );

      final source = repository.sourceFor('journey-42');

      expect(source.sourceKey, 'journey:journey-42');
      expect(source.owner, 'Journeys');
      expect(source.path, 'api/v1/me/journeys/journey-42/');
      expect(source.projectionKind, 'personal.journey.detail');
      expect(source.resourceKey, 'journey-42');
      expect(source.category.name, 'keyedDetail');
    },
  );

  test(
    'Journey selector presents server Readiness without recomputing it',
    () async {
      final now = DateTime.utc(2026, 9, 30, 12);
      final projection = StoredProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'journey-1',
        schemaVersion: 1,
        receivedAt: now,
        payload: const {
          'representation': {
            'title': 'Inscription formation',
            'kind_label': 'Démarche',
            'summary': 'Préparer votre inscription.',
          },
          'state': {'code': 'active', 'label': 'En cours'},
          'readiness': {
            'state': 'action_required',
            'ready': [
              {
                'key': 'proof.ok',
                'summary': 'Pièce déjà en ordre',
                'reason': 'satisfied',
              },
            ],
            'actor_interventions': [
              {
                'key': 'form_request.form-1',
                'summary': 'Répondre au formulaire',
                'reason': 'form_response_required',
                'next': {
                  'label': 'Compléter',
                  'link': '/api/v1/questionnaires/requests/form-1/',
                },
              },
            ],
            'waiting': [],
            'blockers': [],
            'next': {
              'key': 'form_request.form-1',
              'label': 'Répondre au formulaire',
              'link': '/api/v1/questionnaires/requests/form-1/',
            },
          },
          'forms': [
            {
              'id': 'form-1',
              'required': true,
              'state': 'requested',
              'capabilities': ['complete_form'],
              'links': {
                'detail': '/api/v1/questionnaires/requests/form-1/',
                'save': '/api/v1/questionnaires/requests/form-1/save/',
                'submit': '/api/v1/questionnaires/requests/form-1/submit/',
              },
            },
          ],
          'requirements': [
            {'id': 'req-1', 'label': 'Passeport', 'state': 'satisfied'},
          ],
          'activity': {'id': 'activity-1', 'title': 'Formation'},
          'occurrence': null,
          'capabilities': ['complete_form'],
        },
      );

      final result = const JourneyDetailSelector().select(
        projection: projection,
        source: const JourneySourceState(lastSuccessAt: null),
        now: now,
      );

      expect(result.readinessState, 'action_required');
      expect(
        result.actorInterventions.single.summary,
        'Répondre au formulaire',
      );
      expect(result.ready.single.summary, 'Pièce déjà en ordre');
      expect(result.nextActionLabel, 'Répondre au formulaire');
      expect(result.forms.single.canComplete, isTrue);
      expect(
        result.forms.single.submitLink,
        '/api/v1/questionnaires/requests/form-1/submit/',
      );
      expect(result.requirements.single.state, 'satisfied');
      expect(result.freshness, FreshnessState.fresh);
    },
  );

  test(
    'Journey exposes occurrence depths only from owner links and capabilities',
    () {
      final now = DateTime.utc(2026, 10, 9, 10);
      final projection = StoredProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'journey-1',
        schemaVersion: 1,
        receivedAt: now,
        payload: const {
          'representation': {'title': 'Voyage Lubumbashi — Kolwezi'},
          'state': {'code': 'confirmed', 'label': 'Confirmée'},
          'readiness': {
            'state': 'ready',
            'ready': [],
            'actor_interventions': [],
            'waiting': [],
            'blockers': [],
          },
          'forms': [],
          'requirements': [],
          'activity': {
            'id': 'activity-1',
            'title': 'Voyage Lubumbashi — Kolwezi',
          },
          'occurrence': {
            'id': 'occurrence-1',
            'label': 'Départ 14 h',
            'state': 'scheduled',
          },
          'access': {
            'id': 'access-1',
            'state': 'valid',
            'link': '/api/v1/me/accesses/access-1/',
          },
          'capabilities': ['open_day_of', 'open_live'],
          'links': {
            'activity': '/api/v1/activities/activity-1/',
            'occurrence': '/api/v1/occurrences/occurrence-1/',
            'day_of': '/api/v1/me/occurrences/occurrence-1/day-of/',
            'live': '/api/v1/me/occurrences/occurrence-1/live/',
          },
        },
      );

      final result = const JourneyDetailSelector().select(
        projection: projection,
        source: JourneySourceState.unknown,
        now: now,
      );

      expect(result.activity?.link, '/api/v1/activities/activity-1/');
      expect(result.occurrence?.link, '/api/v1/occurrences/occurrence-1/');
      expect(result.access?.id, 'access-1');
      expect(result.access?.link, '/api/v1/me/accesses/access-1/');
      expect(result.dayOfLink, '/api/v1/me/occurrences/occurrence-1/day-of/');
      expect(result.liveLink, '/api/v1/me/occurrences/occurrence-1/live/');
    },
  );

  test(
    'Journey never grants Jour J or Live from links without capabilities',
    () {
      final now = DateTime.utc(2026, 10, 9, 10);
      final projection = StoredProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'journey-1',
        schemaVersion: 1,
        receivedAt: now,
        payload: const {
          'representation': {'title': 'Démarche'},
          'state': {'code': 'active'},
          'readiness': {
            'state': 'waiting',
            'ready': [],
            'actor_interventions': [],
            'waiting': [],
            'blockers': [],
          },
          'forms': [],
          'requirements': [],
          'occurrence': {'id': 'occurrence-1', 'label': 'Départ 14 h'},
          'capabilities': [],
          'links': {
            'day_of': '/api/v1/me/occurrences/occurrence-1/day-of/',
            'live': '/api/v1/me/occurrences/occurrence-1/live/',
          },
        },
      );

      final result = const JourneyDetailSelector().select(
        projection: projection,
        source: JourneySourceState.unknown,
        now: now,
      );

      expect(result.dayOfLink, isNull);
      expect(result.liveLink, isNull);
    },
  );

  test('Journey capability absence never grants complete_form locally', () {
    final now = DateTime.utc(2026, 9, 30, 12);
    final projection = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-1',
      schemaVersion: 1,
      receivedAt: now,
      payload: const {
        'representation': {'title': 'Démarche'},
        'state': {'code': 'active'},
        'readiness': {
          'state': 'action_required',
          'ready': [],
          'actor_interventions': [],
          'waiting': [],
          'blockers': [],
        },
        'forms': [
          {
            'id': 'form-1',
            'required': true,
            'state': 'requested',
            'capabilities': [],
            'links': {'detail': '/api/v1/questionnaires/requests/form-1/'},
          },
        ],
        'requirements': [],
        'capabilities': [],
      },
    );

    final result = const JourneyDetailSelector().select(
      projection: projection,
      source: JourneySourceState.unknown,
      now: now,
    );

    expect(result.forms.single.canComplete, isFalse);
    expect(result.canCompleteAnyForm, isFalse);
  });
  test('N3 stays locally readable and presents only owner steps', () {
    final now = DateTime.utc(2026, 11, 9, 10);
    final local = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-1',
      schemaVersion: 1,
      receivedAt: now,
      payload: const {
        'identity': {'kind': 'journey', 'workflow': 'registration'},
        'representation': {
          'title': 'Recevoir mon badge',
          'kind_label': 'Inscription',
          'summary': 'Recevoir mon badge',
        },
        'state': {'code': 'in_progress', 'label': 'En cours'},
        'readiness': {
          'state': 'waiting',
          'ready': [],
          'actor_interventions': [],
          'waiting': [
            {'key': 'review', 'summary': 'Réponse de l’organisateur'},
          ],
          'blockers': [],
        },
        'steps': [
          {
            'id': 'step-1',
            'title': 'Envoyer mon inscription',
            'kind': 'submission',
            'status': 'completed',
            'depends_on': [],
          },
          {
            'id': 'step-2',
            'title': 'Recevoir la décision',
            'kind': 'decision',
            'status': 'pending',
            'depends_on': ['step-1'],
          },
        ],
        'forms': [],
        'requirements': [],
        'capabilities': [],
      },
    );

    final result = const JourneyDetailSelector().select(
      projection: local,
      source: const JourneySourceState(lastErrorCode: 'network_unavailable'),
      now: now,
    );

    expect(result.available, isTrue);
    expect(result.title, 'Recevoir mon badge');
    expect(result.summary, isNull);
    expect(result.workflowKind, 'registration');
    expect(result.stateCode, 'in_progress');
    expect(result.steps.length, 2);
    expect(result.steps.first.isCompleted, isTrue);
    expect(result.steps.last.dependsOn, ['step-1']);
    expect(result.steps.last.isCompleted, isFalse);
    expect(result.waiting.single.summary, 'Réponse de l’organisateur');
  });

  test('N3 without owner steps does not invent milestones or completion', () {
    final now = DateTime.utc(2026, 11, 9, 10);
    final projection = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-2',
      schemaVersion: 1,
      receivedAt: now,
      payload: const {
        'representation': {'title': 'Une demande'},
        'state': {'code': 'rejected', 'label': 'Rejetée'},
        'readiness': {
          'state': 'waiting',
          'ready': [],
          'actor_interventions': [],
          'waiting': [],
          'blockers': [],
        },
        'capabilities': [],
      },
    );
    final result = const JourneyDetailSelector().select(
      projection: projection,
      source: JourneySourceState.unknown,
      now: now,
    );
    expect(result.steps, isEmpty);
    expect(result.isTerminal, isTrue);
    expect(result.nextActionLabel, isNull);
  });

  testWidgets(
    'Journey N3 renders from ProfileStore without any remote client',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      await store.putProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'journey-local',
        schemaVersion: 1,
        payload: const {
          'identity': {'workflow': 'registration'},
          'representation': {'title': 'Recevoir mon badge'},
          'state': {'code': 'in_progress', 'label': 'En cours'},
          'readiness': {
            'state': 'waiting',
            'ready': [],
            'actor_interventions': [],
            'waiting': [],
            'blockers': [],
          },
          'steps': [
            {
              'id': 'step-local',
              'title': 'Envoyer ma demande',
              'kind': 'submission',
              'status': 'in_progress',
              'depends_on': [],
            },
          ],
          'forms': [],
          'requirements': [],
          'capabilities': [],
        },
      );
      final repository = JourneyRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: JourneyDetailScreen(
            journeyId: 'journey-local',
            repository: repository,
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
      expect(find.text('MON OBJECTIF'), findsOneWidget);
      expect(find.text('Recevoir mon badge'), findsOneWidget);
      expect(find.text('Où j’en suis'), findsOneWidget);
      expect(find.text('Envoyer ma demande'), findsOneWidget);
    },
  );

  test('N3 working-set IDs use only the acquired personal owner facts', () {
    final id = '00000000-0000-0000-0000-000000000123';
    final projection = StoredProjection(
      kind: 'personal.ongoing',
      resourceKey: '',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 9),
      payload: {
        'items': [
          {
            'source': {'kind': 'journey', 'id': id},
          },
          {
            'source': {'kind': 'journey', 'id': id},
          },
          {
            'source': {'kind': 'activity', 'id': 'activity-1'},
          },
          {
            'source': {'kind': 'journey', 'id': '../unauthorized'},
          },
        ],
      },
    );
    expect(JourneyRepository.knownJourneyIdsFromOngoing(projection), [id]);
    expect(
      JourneyRepository.knownJourneyIdsFromOngoing(projection, limit: 0),
      isEmpty,
    );
    expect(JourneyRepository.knownJourneyIdsFromOngoing(null), isEmpty);
  });

  test('Lot B selects owner payments, requests, named forms and timing', () {
    final now = DateTime.utc(2026, 11, 9, 10);
    final projection = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-b',
      schemaVersion: 1,
      receivedAt: now,
      payload: const {
        'identity': {'workflow': 'registration'},
        'representation': {'title': 'Recevoir un badge'},
        'state': {'code': 'in_progress', 'label': 'En cours'},
        'readiness': {
          'state': 'action_required',
          'ready': [
            {'key': 'ready', 'summary': 'Inscription reçue'},
          ],
          'actor_interventions': [
            {
              'key': 'form_request.request-1',
              'summary': 'Compléter le formulaire',
              'next': {
                'label': 'Répondre',
                'link': '/api/v1/questionnaires/requests/request-1/',
              },
            },
          ],
          'waiting': [],
          'blockers': [],
        },
        'requests': {
          'pending': [
            {'id': 'request', 'state': 'pending'},
          ],
          'rejected': [],
        },
        'forms': [
          {
            'id': 'request-1',
            'title': 'Informations du participant',
            'required': true,
            'state': 'requested',
            'capabilities': ['complete_form'],
            'links': {'detail': '/api/v1/questionnaires/requests/request-1/'},
          },
        ],
        'requirements': [
          {
            'id': 'assessment-1',
            'label': 'Pièce d’identité',
            'required': true,
            'state': 'missing',
            'consequence': 'blocking',
            'link': '/api/v1/me/journeys/journey-b/requirements/assessment-1/',
          },
        ],
        'payment': {
          'obligations': [
            {
              'id': 'obligation-1',
              'amount': '15.00',
              'currency': 'USD',
              'state': 'pending',
            },
            {
              'id': 'obligation-2',
              'amount': '5.00',
              'currency': 'USD',
              'state': 'satisfied',
            },
          ],
        },
        'occurrence': {
          'id': 'occurrence-1',
          'timing': {
            'start_date': '2026-12-11',
            'start_time': '13:06:00',
            'timezone': 'Africa/Lubumbashi',
          },
          'place': {'name': 'Centre de conférence', 'locality': 'Lubumbashi'},
        },
        'capabilities': [],
      },
    );
    final result = const JourneyDetailSelector().select(
      projection: projection,
      source: JourneySourceState.unknown,
      now: now,
    );
    expect(result.pendingRequests, 1);
    expect(result.forms.single.title, 'Informations du participant');
    expect(result.forms.single.canComplete, isTrue);
    expect(result.requirements.single.isRequired, isTrue);
    expect(result.requirements.single.consequence, 'blocking');
    expect(result.payments.length, 2);
    expect(result.payments.last.obligationId, 'obligation-2');
    expect(result.practical?.startDate, '2026-12-11');
    expect(result.practical?.placeName, 'Centre de conférence');
    expect(
      result.actorInterventions.single.nextLink,
      '/api/v1/questionnaires/requests/request-1/',
    );
  });

  test(
    'Lot B previews only Preparation resources from its local projection',
    () {
      final preview = StoredProjection(
        kind: 'preparation.journey.resources',
        resourceKey: 'journey-b',
        schemaVersion: 1,
        receivedAt: DateTime.utc(2026, 11, 9),
        payload: const {
          'items': [
            {'id': 'r1', 'title': 'Guide de participation', 'kind': 'file'},
            {'id': 'r2', 'title': 'Consignes pratiques', 'kind': 'text'},
            {'id': '', 'title': 'Incomplete', 'kind': 'file'},
          ],
        },
      );
      final items = JourneyResourcePreview.fromProjection(preview);
      expect(items.length, 2);
      expect(items.first.kind, 'file');
      expect(items.last.title, 'Consignes pratiques');
      expect(JourneyResourcePreview.fromProjection(null), isEmpty);
    },
  );

  testWidgets(
    'Lot B renders Preparation preview from the same Profile database',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-b');
      await store.putProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'journey-b',
        schemaVersion: 1,
        payload: const {
          'representation': {'title': 'Préparer ma visite'},
          'state': {'code': 'in_progress', 'label': 'En cours'},
          'readiness': {
            'state': 'ready',
            'ready': [],
            'actor_interventions': [],
            'waiting': [],
            'blockers': [],
          },
          'resources': {
            'link': '/api/v1/preparation/journeys/journey-b/resources/',
          },
          'forms': [],
          'requirements': [],
          'capabilities': [],
        },
      );
      await store.putProjection(
        kind: PreparationResourcesRepository.projectionKind,
        resourceKey: 'journey-b',
        schemaVersion: 1,
        payload: const {
          'items': [
            {
              'id': 'resource-1',
              'kind': 'file',
              'title': 'Guide de préparation',
            },
          ],
        },
      );
      final journeys = JourneyRepository(
        database: database,
        store: store,
        profileId: 'profile-b',
      );
      final preparation = PreparationResourcesRepository(
        database: database,
        store: store,
        profileId: 'profile-b',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: JourneyDetailScreen(
            journeyId: 'journey-b',
            repository: journeys,
            resourcesRepository: preparation,
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
      await tester.scrollUntilVisible(
        find.text('Guide de préparation'),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Guide de préparation'), findsOneWidget);
    },
  );

  test(
    'Lot B prepares only locally known owner Form and Requirement links',
    () {
      const journeyId = '00000000-0000-0000-0000-000000000001';
      const formId = '00000000-0000-0000-0000-000000000002';
      const requirementId = '00000000-0000-0000-0000-000000000003';
      final local = StoredProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: journeyId,
        schemaVersion: 1,
        receivedAt: DateTime.utc(2026, 11, 9),
        payload: const {
          'forms': [
            {
              'id': formId,
              'links': {'detail': '/api/v1/questionnaires/requests/$formId/'},
            },
            {
              'id': formId,
              'links': {'detail': 'https://external.example.invalid/forged'},
            },
          ],
          'requirements': [
            {
              'id': requirementId,
              'link':
                  '/api/v1/me/journeys/$journeyId/requirements/$requirementId/',
            },
            {
              'id': formId,
              'link': '/api/v1/me/journeys/another/requirements/$formId/',
            },
          ],
        },
      );
      expect(JourneyRepository.knownFormLinksFromDetail(local), {
        formId: '/api/v1/questionnaires/requests/$formId/',
      });
      expect(
        JourneyRepository.knownRequirementLinksFromDetail(
          local,
          journeyId: journeyId,
        ),
        {
          requirementId:
              '/api/v1/me/journeys/$journeyId/requirements/$requirementId/',
        },
      );
      expect(
        JourneyRepository.knownFormLinksFromDetail(local, limit: 0),
        isEmpty,
      );
    },
  );
}
