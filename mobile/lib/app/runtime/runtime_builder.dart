import '../../auth/token_store.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../features/access/access_assembly.dart';
import '../../features/continuity/continuity_assembly.dart';
import '../../features/day_of/day_of_assembly.dart';
import '../../features/live/live_repository.dart';
import '../../features/discovery/discovery_assembly.dart';
import '../../features/discovery/discovery_repository.dart';
import '../../features/journey/journey_assembly.dart';
import '../../features/preparation/preparation_assembly.dart';
import '../../features/questionnaires/questionnaire_assembly.dart';
import '../../features/resources/resource_repository.dart';
import '../../features/space/space_assembly.dart';
import '../../features/space/space_occurrence_repository.dart';
import '../../network/makolo_api_client.dart';
import '../../navigation/destination.dart';
import '../../notifications/notification_repository.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/location/geo_search_gateway.dart';
import '../../presentation/mps/mps_repository.dart';
import '../../repositories/draft_repository.dart';
import '../../repositories/interoperability_repository.dart';
import '../../repositories/personal_repository.dart';
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
  final geoSearch = config.geocoding.enabled
      ? MapTilerGeoSearchGateway(apiKey: config.geocoding.apiKey!)
      : null;

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
  sync
    ?..registerPreparedSource(
      space.inventorySource(),
      acquire: space.refreshInventory,
    )
    ..registerPreparedSource(
      discovery.itemsSource(const DiscoveryQuery()),
      acquire: () => discovery.refreshItems(const DiscoveryQuery()),
    )
    ..registerPreparedSource(
      accesses.collectionSourceFor(relationship: 'beneficiary', offset: 0),
    )
    ..registerPreparedSource(
      resources.collectionSourceFor(query: '', offset: 0),
    )
    ..registerPreparedSource(continuity.conversations.listSource())
    ..registerPreparedSource(notifications.listSource())
    ..registerPreparedSource(continuity.history.sourceFor(offset: 0));

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
    requirements: preparation.requirements,
    preparationResources: preparation.resources,
    resources: resources,
    questionnaires: questionnaires.repository,
    drafts: drafts,
    questionnaireSubmit: questionnaires.submit,
    outbox: outbox,
    outboxProcessor: questionnaires.outboxProcessor,
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
