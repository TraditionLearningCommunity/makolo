import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
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

  test('Journey exposes occurrence depths only from owner links and capabilities', () {
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
        'activity': {'id': 'activity-1', 'title': 'Voyage Lubumbashi — Kolwezi'},
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
    expect(
      result.dayOfLink,
      '/api/v1/me/occurrences/occurrence-1/day-of/',
    );
    expect(
      result.liveLink,
      '/api/v1/me/occurrences/occurrence-1/live/',
    );
  });

  test('Journey never grants Jour J or Live from links without capabilities', () {
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
  });

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
}
