import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/questionnaires/questionnaire_repository.dart';
import 'package:makolo_mobile/features/questionnaires/questionnaire_submit_coordinator.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_processor.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Map<String, dynamic> requestPayload({
  String requestStatus = 'requested',
  String? responseStatus = 'draft',
  Map<String, dynamic> answers = const {'name': 'Alice'},
}) {
  return {
    'id': 'request-1',
    'journey_id': 'journey-1',
    'target_profile_id': null,
    'required': true,
    'status': requestStatus,
    'opens_at': null,
    'due_at': '2026-10-10T12:00:00Z',
    'form_version': {
      'id': 'version-1',
      'form_key': 'registration',
      'version': 1,
      'title': 'Inscription',
      'description': 'Informations nécessaires',
      'questions': [
        {
          'key': 'name',
          'label': 'Nom',
          'help_text': 'Votre nom',
          'type': 'short_text',
          'position': 0,
          'required': true,
          'min_length': 2,
          'max_length': 40,
          'min_value': null,
          'max_value': null,
          'choices': [],
        },
        {
          'key': 'mode',
          'label': 'Mode',
          'help_text': '',
          'type': 'single_choice',
          'position': 1,
          'required': true,
          'min_length': null,
          'max_length': null,
          'min_value': null,
          'max_value': null,
          'choices': ['A', 'B'],
        },
      ],
    },
    'response': responseStatus == null
        ? null
        : {
            'id': 'response-1',
            'status': responseStatus,
            'submitted_at': responseStatus == 'submitted'
                ? '2026-09-30T12:05:00Z'
                : null,
            'answers': answers,
          },
  };
}

void main() {
  test(
    'Questionnaire direct owner payload becomes a keyed local projection',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((request) async {
        expect(request.url.path, '/api/v1/questionnaires/requests/request-1/');
        return MockResponse(jsonEncode(requestPayload()), 200);
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final sync = SyncEngine(
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final repository = QuestionnaireRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: sync,
      );

      await repository.refresh(
        requestId: 'request-1',
        detailPath: '/api/v1/questionnaires/requests/request-1/',
      );

      final stored = await repository.readDetail('request-1');
      final parsed = await repository.readParsed('request-1');
      expect(stored?.kind, QuestionnaireRepository.projectionKind);
      expect(stored?.resourceKey, 'request-1');
      expect(parsed?.title, 'Inscription');
      expect(parsed?.questions.map((row) => row.type), [
        QuestionnaireQuestionType.shortText,
        QuestionnaireQuestionType.singleChoice,
      ]);
      expect(parsed?.questions.first.minLength, 2);
      expect(parsed?.questions.last.choices, ['A', 'B']);
      expect(parsed?.answers['name'], 'Alice');
    },
  );

  test(
    'local Questionnaire draft survives read/watch and remains Profile scoped',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final outboxA = OutboxRepository(database, 'profile-a');
      final draftsA = DraftRepository(
        database: database,
        outbox: outboxA,
        profileId: 'profile-a',
      );
      final draftsB = DraftRepository(
        database: database,
        outbox: OutboxRepository(database, 'profile-b'),
        profileId: 'profile-b',
      );

      await draftsA.saveLocal(
        draftId: 'questionnaire:request-1',
        owner: QuestionnaireSubmitCoordinator.owner,
        resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
        resourceId: 'request-1',
        payload: const {
          'answers': {'name': 'Local answer'},
        },
      );

      final read = await draftsA.read(
        owner: QuestionnaireSubmitCoordinator.owner,
        resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
        resourceId: 'request-1',
      );
      final watched = await draftsA
          .watch(
            owner: QuestionnaireSubmitCoordinator.owner,
            resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
            resourceId: 'request-1',
          )
          .first;
      final other = await draftsB.read(
        owner: QuestionnaireSubmitCoordinator.owner,
        resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
        resourceId: 'request-1',
      );

      expect(read?.payload['answers'], {'name': 'Local answer'});
      expect(watched?.payload['answers'], {'name': 'Local answer'});
      expect(other, isNull);
    },
  );

  test(
    'submit intent saves then submits, deletes draft and refreshes Journey',
    () async {
      var journeyReads = 0;
      var detailReads = 0;
      var saves = 0;
      var submits = 0;
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        deviceId: 'device-a',
      );
      final client = MockClient((request) async {
        switch (request.url.path) {
          case '/api/v1/questionnaires/requests/request-1/save/':
            saves += 1;
            return MockResponse(jsonEncode(requestPayload()), 200);
          case '/api/v1/questionnaires/requests/request-1/submit/':
            submits += 1;
            return MockResponse(
              jsonEncode(
                requestPayload(
                  requestStatus: 'completed',
                  responseStatus: 'submitted',
                ),
              ),
              200,
            );
          case '/api/v1/questionnaires/requests/request-1/':
            detailReads += 1;
            return MockResponse(
              jsonEncode(
                requestPayload(
                  requestStatus: 'completed',
                  responseStatus: 'submitted',
                ),
              ),
              200,
            );
          case '/api/v1/me/journeys/journey-1/':
            journeyReads += 1;
            return MockResponse(
              jsonEncode({
                'meta': {
                  'projection': 'personal.journey.detail',
                  'schema_version': 1,
                  'generated_at': '2026-09-30T12:10:00Z',
                },
                'data': {
                  'representation': {'title': 'Journey refreshed'},
                  'state': {'code': 'active'},
                  'readiness': {
                    'state': 'ready',
                    'ready': [],
                    'actor_interventions': [],
                    'waiting': [],
                    'blockers': [],
                  },
                  'forms': [],
                  'requirements': [],
                  'capabilities': [],
                },
              }),
              200,
            );
          default:
            throw StateError('unexpected route ${request.url.path}');
        }
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: client.dio,
        tokenStore: tokens,
      );
      final sync = SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final outbox = OutboxRepository(database, 'profile-a');
      final drafts = DraftRepository(
        database: database,
        outbox: outbox,
        profileId: 'profile-a',
      );
      final journeys = JourneyRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: sync,
      );
      final questionnaires = QuestionnaireRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: sync,
      );
      final coordinator = QuestionnaireSubmitCoordinator(
        api: api,
        tokens: tokens,
        outbox: outbox,
        drafts: drafts,
        questionnaires: questionnaires,
        journeys: journeys,
      );
      final processor = OutboxProcessor(
        repository: outbox,
        handlers: {
          QuestionnaireSubmitCoordinator.operationKind: coordinator.handler,
        },
        reconcilers: {
          QuestionnaireSubmitCoordinator.operationKind: coordinator.reconciler,
        },
      );
      const links = QuestionnaireOwnerLinks(
        detail: '/api/v1/questionnaires/requests/request-1/',
        save: '/api/v1/questionnaires/requests/request-1/save/',
        submit: '/api/v1/questionnaires/requests/request-1/submit/',
      );

      expect(
        await coordinator.enqueue(
          requestId: 'request-1',
          journeyId: 'journey-1',
          answers: const {'name': 'Alice', 'mode': 'A'},
          links: links,
        ),
        isTrue,
      );
      expect(
        await coordinator.enqueue(
          requestId: 'request-1',
          journeyId: 'journey-1',
          answers: const {'name': 'Alice', 'mode': 'A'},
          links: links,
        ),
        isFalse,
        reason: 'double submit must collapse into one active intent',
      );

      await processor.run();

      final operation =
          (await database.select(database.outboxOperations).get()).single;
      expect(operation.replayPolicy, ReplayPolicy.refetchBeforeRetry.wireValue);
      expect(operation.state, OutboxState.confirmed.wireValue);
      expect(saves, 1);
      expect(submits, 1);
      expect(detailReads, 1);
      expect(journeyReads, 1);
      expect(
        await drafts.read(
          owner: QuestionnaireSubmitCoordinator.owner,
          resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
          resourceId: 'request-1',
        ),
        isNull,
      );
      expect(
        (await store.readProjection(
          JourneyRepository.projectionKind,
          resourceKey: 'journey-1',
        ))?.payload['representation'],
        {'title': 'Journey refreshed'},
      );
    },
  );

  test(
    'awaiting confirmation is reconciled after restart-like processor run',
    () async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final repository = OutboxRepository(database, 'profile-a');
      await repository.enqueue(
        operationId: 'op-1',
        deviceInstanceId: 'device-a',
        operationKind: 'questionnaire.form.submit',
        owner: 'Questionnaires',
        resourceKind: 'form_request',
        resourceId: 'request-1',
        payload: const {},
        intentId: 'intent-1',
        replayPolicy: ReplayPolicy.refetchBeforeRetry,
      );
      await repository.setState('op-1', OutboxState.awaitingConfirmation);

      var reconciled = 0;
      final processor = OutboxProcessor(
        repository: repository,
        handlers: {
          'questionnaire.form.submit': (_) async {
            fail('awaiting confirmation must reconcile before any replay');
          },
        },
        reconcilers: {
          'questionnaire.form.submit': (_) async {
            reconciled += 1;
            return OutboxResolution.confirmed;
          },
        },
      );

      await processor.run();

      final row =
          (await database.select(database.outboxOperations).get()).single;
      expect(reconciled, 1);
      expect(row.state, OutboxState.confirmed.wireValue);
    },
  );
}
