import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/token_store.dart';
import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../features/access/access_repository.dart';
import '../features/continuity/conversation_repository.dart';
import '../features/continuity/history_repository.dart';
import '../features/continuity/objective_repository.dart';
import '../features/discovery/discovery_repository.dart';
import '../features/day_of/day_of_repository.dart';
import '../features/journey/journey_repository.dart';
import '../features/preparation/preparation_repository.dart';
import '../features/questionnaires/questionnaire_repository.dart';
import '../features/questionnaires/questionnaire_submit_coordinator.dart';
import '../network/makolo_api_client.dart';
import '../platform/location/location_capability.dart';
import '../platform/location/location_service.dart';
import '../platform/permissions/permission_gateway.dart';
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
    this.discovery,
    this.location,
    this.accesses,
    this.dayOf,
    this.journeys,
    this.objectives,
    this.history,
    this.conversations,
    this.requirements,
    this.preparationResources,
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
  final DiscoveryRepository? discovery;
  final LocationCapability? location;
  final AccessRepository? accesses;
  final DayOfRepository? dayOf;
  final JourneyRepository? journeys;
  final ObjectiveRepository? objectives;
  final HistoryRepository? history;
  final ConversationRepository? conversations;
  final RequirementRepository? requirements;
  final PreparationResourcesRepository? preparationResources;
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

final runtimeConfigProvider = Provider<MakoloRuntimeConfig>(
  (ref) => MakoloRuntimeConfig.fromEnvironment(),
);

final appRuntimeProvider = FutureProvider<AppRuntime>((ref) async {
  final tokens = ref.watch(tokenStoreProvider);
  final recovery = ref.watch(sessionRecoveryProvider);
  final config = ref.watch(runtimeConfigProvider);
  final launchPreferences = await FileLaunchPreferencesStore.open();
  final interactions = await ResumableInteractionStore.open();
  final session = await tokens.readSession();
  final baseUri = config.api.baseUri;
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
  final location = const LocationCapability(
    permissions: PermissionHandlerGateway(),
    service: GeolocatorLocationService(),
  );
  final discovery = api == null
      ? null
      : DiscoveryRepository(
          database: database,
          store: store,
          profileId: profileId,
          api: api,
          sync: sync,
        );
  final accesses = AccessRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
    api: api,
  );
  final dayOf = DayOfRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final journeys = JourneyRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final objectives = ObjectiveRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final history = HistoryRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final conversations = ConversationRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final requirements = RequirementRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final preparationResources = PreparationResourcesRepository(
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
    discovery: discovery,
    location: location,
    accesses: accesses,
    dayOf: dayOf,
    journeys: journeys,
    objectives: objectives,
    history: history,
    conversations: conversations,
    requirements: requirements,
    preparationResources: preparationResources,
    questionnaires: questionnaires,
    drafts: drafts,
    questionnaireSubmit: questionnaireSubmit,
    outbox: outbox,
    outboxProcessor: outboxProcessor,
    sync: sync,
  );
});
