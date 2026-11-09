import '../../auth/token_store.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../features/access/access_assembly.dart';
import '../../features/continuity/continuity_assembly.dart';
import '../../features/continuity/objective_repository.dart';
import '../../features/continuity/conversation_local_delivery.dart';
import '../../features/continuity/conversation_repository.dart';
import '../../features/day_of/day_of_assembly.dart';
import '../../features/live/live_repository.dart';
import '../../features/discovery/discovery_assembly.dart';
import '../../features/discovery/discovery_repository.dart';
import '../../features/journey/journey_assembly.dart';
import '../../features/preparation/preparation_assembly.dart';
import '../../features/questionnaires/questionnaire_assembly.dart';
import '../../features/questionnaires/questionnaire_submit_coordinator.dart';
import '../../features/resources/resource_repository.dart';
import '../../features/resources/trust_resource_repository.dart';
import '../../features/space/space_assembly.dart';
import '../../features/space/space_occurrence_repository.dart';
import '../../network/makolo_api_client.dart';
import '../../navigation/destination.dart';
import '../../notifications/notification_repository.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/location/geo_search_gateway_factory.dart';
import '../../platform/routing/routing_gateway_factory.dart';
import '../../presentation/mps/mps_repository.dart';
import '../../repositories/draft_repository.dart';
import '../../repositories/interoperability_repository.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/outbox/outbox_processor.dart';
import '../../sync/outbox/outbox_repository.dart';
import '../../sync/sync_engine.dart';
import '../environment.dart';
import '../launch_preferences.dart';
import '../resumable_interaction_store.dart';
import '../session_recovery.dart';
import 'actor_context_controller.dart';
import 'app_runtime.dart';

typedef LocationCapabilityFactory = LocationCapability Function(
  MakoloRuntimeConfig config,
);

Future<AppRuntime> buildAppRuntime({
  required TokenStore tokens,
  required SessionRecoveryController recovery,
  required MakoloRuntimeConfig config,
  required LocationCapabilityFactory locationFactory,
}) async {
  final launchPreferences = await FileLaunchPreferencesStore.open();
  final preferenceSnapshot = await launchPreferences.read();
  final preferences = AppPreferencesController(
    store: launchPreferences,
    initial: preferenceSnapshot,
  );
  final interactions = await ResumableInteractionStore.open();
  final session = await tokens.readSession();
  // Public snapshots live outside every personal Profile database.
  const publicScope = '__makolo_public_v1__';
  final publicDatabase = await MakoloDatabase.openForProfile(publicScope);
  final publicStore = ProfileStore(publicDatabase, publicScope);
  final baseUri = config.api.baseUri;
  final api = baseUri == null
      ? null
      : MakoloApiClient(baseUri: baseUri, tokenStore: tokens);
  final geoSearch = createGeoSearchGateway(
    enabled: config.geocoding.enabled,
    provider: config.geocoding.provider,
    apiKey: config.geocoding.apiKey,
    endpoint: config.geocoding.endpoint,
  );

  final routing = createRoutingGateway(
    enabled: config.routing.enabled,
    provider: config.routing.provider,
    apiKey: config.routing.apiKey,
    endpoint: config.routing.endpoint,
  );

  final profileId = session?.profileId;
  if (profileId == null) {
    return AppRuntime(
      tokens: tokens,
      session: session,
      recovery: recovery,
      launchPreferences: launchPreferences,
      preferences: preferences,
      config: config,
      interactions: interactions,
      publicDatabase: publicDatabase,
      publicStore: publicStore,
      api: api,
      location: locationFactory(config),
      geoSearch: geoSearch,
      routing: routing,
    );
  }

  // The persisted actor is a local preference, not server authority.
  // Restore it before selecting the first door; never force a Space user
  // through the personal shell after an ordinary app restart.
  final actorContext = await ActorContextController.restore(
    profileId: profileId,
    store: launchPreferences,
  );
  recovery.restoreLaunchLocation(
    restoredShellPath(
      actorContext.value,
      await launchPreferences.readShellLocation(profileId),
    ),
  );
  final database = await MakoloDatabase.openForProfile(profileId);
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

  final journeys = buildJourneyRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final continuity = buildContinuityAssembly(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );
  final preparation = buildPreparationAssembly(
    database: database,
    store: store,
    profileId: profileId,
    api: api,
    sync: sync,
  );
  final questionnaires = buildQuestionnaireAssembly(
    database: database,
    store: store,
    profileId: profileId,
    api: api,
    tokens: tokens,
    outbox: outbox,
    drafts: drafts,
    journeys: journeys,
    sync: sync,
  );
  // One owner-scoped outbox processor dispatches both Questionnaire and
  // Conversation operations. C3_bus never creates a private second queue.
  final conversationDelivery = api == null
      ? null
      : ConversationLocalDelivery(
          database: database,
          drafts: drafts,
          outbox: outbox,
          tokens: tokens,
          api: api,
          profileId: profileId,
          refreshDetail: (conversationId, focusedPointId) => continuity
              .conversations
              .refreshDetail(conversationId, focusPointId: focusedPointId),
          mediaMime: ConversationRepository.mediaMime,
        );
  continuity.conversations.delivery = conversationDelivery;
  final outboxProcessor = api == null
      ? null
      : OutboxProcessor(
          repository: outbox,
          handlers: {
            if (questionnaires.submit != null)
              QuestionnaireSubmitCoordinator.operationKind:
                  questionnaires.submit!.handler,
            if (conversationDelivery != null)
              ConversationLocalDelivery.operationKind:
                  conversationDelivery.handle,
          },
          reconcilers: {
            if (questionnaires.submit != null)
              QuestionnaireSubmitCoordinator.operationKind:
                  questionnaires.submit!.reconciler,
          },
          expectedOwners: {
            if (questionnaires.submit != null)
              QuestionnaireSubmitCoordinator.operationKind:
                  QuestionnaireSubmitCoordinator.owner,
            if (conversationDelivery != null)
              ConversationLocalDelivery.operationKind:
                  ConversationLocalDelivery.owner,
          },
          expectedReplayPolicies: {
            if (questionnaires.submit != null)
              QuestionnaireSubmitCoordinator.operationKind:
                  ReplayPolicy.refetchBeforeRetry,
            if (conversationDelivery != null)
              ConversationLocalDelivery.operationKind: ReplayPolicy.idempotent,
          },
          canDispatch: (operation) async =>
              (await tokens.readSession())?.profileId == operation.profileId,
        );
  conversationDelivery?.requestDispatch = outboxProcessor?.run;

  final discovery = buildDiscoveryRepository(
    database: database,
    store: store,
    profileId: profileId,
    api: api,
    sync: sync,
  );
  final accesses = buildAccessRepository(
    database: database,
    store: store,
    profileId: profileId,
    api: api,
    sync: sync,
  );
  final resources = ResourceRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
    api: api,
  );
  final trustResources = TrustResourceRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
    api: api,
  );
  final space = buildWorkspaceContextRepository(
    database: database,
    store: store,
    profileId: profileId,
    actorContext: actorContext,
    sync: sync,
  );

  final notifications = NotificationRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: sync,
  );

  // A bounded personal working set is registered once at composition time.
  // Refreshing it is owned by SyncLifecycle, not by destination widgets.
  // All definitions reuse the exact source and parser of their repository.
  if (sync != null) {
    sync.registerPreparedSource(
      space.inventorySource(),
      acquire: space.refreshInventory,
    );
    if (discovery != null) {
      sync.registerPreparedSource(
        discovery.itemsSource(const DiscoveryQuery()),
        acquire: () => discovery.refreshItems(const DiscoveryQuery()),
      );
    }
    sync
      ..registerPreparedSource(
        accesses.collectionSourceFor(relationship: 'beneficiary', offset: 0),
      )
      ..registerPreparedSource(
        resources.collectionSourceFor(query: '', offset: 0),
      )
      ..registerPreparedSource(
        trustResources.collectionSourceFor(
          family: TrustResourceFamily.proofs,
          query: '',
          offset: 0,
        ),
      )
      ..registerPreparedSource(
        trustResources.collectionSourceFor(
          family: TrustResourceFamily.titles,
          query: '',
          offset: 0,
        ),
      )
      ..registerPreparedSource(continuity.conversations.listSource())
      ..registerPreparedSource(notifications.listSource())
      ..registerPreparedSource(continuity.history.sourceFor(offset: 0))
      // Only first pages of the user's active objectives: the Profile owner
      // decides membership and deeper pages remain demand-driven.
      ..registerPreparedSource(
        continuity.objectives.collectionSourceFor(
          ObjectiveDepth.project,
          offset: 0,
        ),
      )
      ..registerPreparedSource(
        continuity.objectives.collectionSourceFor(
          ObjectiveDepth.dossier,
          offset: 0,
        ),
      );
  }

  return AppRuntime(
    tokens: tokens,
    session: session,
    recovery: recovery,
    launchPreferences: launchPreferences,
    preferences: preferences,
    config: config,
    interactions: interactions,
    publicDatabase: publicDatabase,
    publicStore: publicStore,
    api: api,
    database: database,
    store: store,
    personal: personal,
    interoperability: interoperability,
    discovery: discovery,
    location: locationFactory(config),
    geoSearch: geoSearch,
    routing: routing,
    accesses: accesses,
    dayOf: buildDayOfRepository(
      database: database,
      store: store,
      profileId: profileId,
      sync: sync,
    ),
    live: LiveRepository(
      database: database,
      store: store,
      profileId: profileId,
      sync: sync,
    ),
    journeys: journeys,
    objectives: continuity.objectives,
    history: continuity.history,
    conversations: continuity.conversations,
    notifications: notifications,
    requirements: preparation.requirements,
    preparationResources: preparation.resources,
    resources: resources,
    trustResources: trustResources,
    questionnaires: questionnaires.repository,
    drafts: drafts,
    questionnaireSubmit: questionnaires.submit,
    outbox: outbox,
    outboxProcessor: outboxProcessor,
    sync: sync,
    actorContext: actorContext,
    mps: MpsPresentationRepository(
      store: store,
      profileId: profileId,
      sync: sync,
    ),
    space: space,
    spaceOccurrences: SpaceOccurrenceRepository(
      database: database,
      store: store,
      profileId: profileId,
      sync: sync,
    ),
  );
}
