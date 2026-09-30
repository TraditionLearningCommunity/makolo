import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/token_store.dart';
import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../features/journey/journey_repository.dart';
import '../features/questionnaires/questionnaire_repository.dart';
import '../features/questionnaires/questionnaire_submit_coordinator.dart';
import '../network/makolo_api_client.dart';
import '../repositories/draft_repository.dart';
import '../repositories/interoperability_repository.dart';
import '../repositories/personal_repository.dart';
import '../sync/outbox/outbox_processor.dart';
import '../sync/outbox/outbox_repository.dart';
import '../sync/sync_engine.dart';
import 'environment.dart';
import 'launch_preferences.dart';
import 'resumable_interaction_store.dart';
import 'session_recovery.dart';

class AppRuntime {
  AppRuntime({
    required this.tokens,
    required this.session,
    required this.recovery,
    this.launchPreferences,
    this.interactions,
    this.api,
    this.database,
    this.store,
    this.personal,
    this.interoperability,
    this.journeys,
    this.questionnaires,
    this.drafts,
    this.questionnaireSubmit,
    this.outbox,
    this.outboxProcessor,
    this.sync,
  });

  final TokenStore tokens;
  final AuthSession? session;
  final SessionRecoveryController recovery;
  final LaunchPreferencesStore? launchPreferences;
  final ResumableInteractionStore? interactions;
  final MakoloApiClient? api;
  final MakoloDatabase? database;
  final ProfileStore? store;
  final PersonalRepository? personal;
  final ProfileInteroperabilityRepository? interoperability;
  final JourneyRepository? journeys;
  final QuestionnaireRepository? questionnaires;
  final DraftRepository? drafts;
  final QuestionnaireSubmitCoordinator? questionnaireSubmit;
  final OutboxRepository? outbox;
  final OutboxProcessor? outboxProcessor;
  final SyncEngine? sync;

  bool get isAuthenticated => session?.profileId != null;
  bool get apiConfigured => api != null;

  Future<void> close() async {
    api?.close();
    await database?.close();
  }
}

final tokenStoreProvider = Provider<TokenStore>(
  (ref) => FlutterSecureTokenStore(),
);

final sessionRecoveryProvider = Provider<SessionRecoveryController>(
  (ref) => SessionRecoveryController(),
);

final appRuntimeProvider = FutureProvider<AppRuntime>((ref) async {
  final tokens = ref.watch(tokenStoreProvider);
  final recovery = ref.watch(sessionRecoveryProvider);
  final launchPreferences = await FileLaunchPreferencesStore.open();
  final interactions = await ResumableInteractionStore.open();
  final session = await tokens.readSession();
  final baseUri = MakoloEnvironment.apiBaseUri;
  final api = baseUri == null
      ? null
      : MakoloApiClient(baseUri: baseUri, tokenStore: tokens);

  final profileId = session?.profileId;
  if (profileId == null) {
    return AppRuntime(
      tokens: tokens,
      session: session,
      recovery: recovery,
      launchPreferences: launchPreferences,
      interactions: interactions,
      api: api,
    );
  }

  final database = await MakoloDatabase.openForProfile(profileId);
  ref.onDispose(() {
    api?.close();
    unawaited(database.close());
  });
  final store = ProfileStore(database, profileId);
  final personal = PersonalRepository(store);
  final interoperability = ProfileInteroperabilityRepository(store);
  final outbox = OutboxRepository(database, profileId);
  final drafts = DraftRepository(
    database: database,
    outbox: outbox,
    profileId: profileId,
  );
  final sync = api == null
      ? null
      : SyncEngine(
          api: api,
          store: store,
          database: database,
          profileId: profileId,
        );
  final journeys = JourneyRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final questionnaires = QuestionnaireRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final questionnaireSubmit = api == null
      ? null
      : QuestionnaireSubmitCoordinator(
          api: api,
          tokens: tokens,
          outbox: outbox,
          drafts: drafts,
          questionnaires: questionnaires,
          journeys: journeys,
        );
  final outboxProcessor = questionnaireSubmit == null
      ? null
      : OutboxProcessor(
          repository: outbox,
          handlers: {
            QuestionnaireSubmitCoordinator.operationKind:
                questionnaireSubmit.handler,
          },
          reconcilers: {
            QuestionnaireSubmitCoordinator.operationKind:
                questionnaireSubmit.reconciler,
          },
        );

  return AppRuntime(
    tokens: tokens,
    session: session,
    recovery: recovery,
    launchPreferences: launchPreferences,
    interactions: interactions,
    api: api,
    database: database,
    store: store,
    personal: personal,
    interoperability: interoperability,
    journeys: journeys,
    questionnaires: questionnaires,
    drafts: drafts,
    questionnaireSubmit: questionnaireSubmit,
    outbox: outbox,
    outboxProcessor: outboxProcessor,
    sync: sync,
  );
});
