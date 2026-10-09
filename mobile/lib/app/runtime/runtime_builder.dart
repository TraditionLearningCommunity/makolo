import '../../auth/token_store.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../features/access/access_assembly.dart';
import '../../features/continuity/continuity_assembly.dart';
import '../../features/day_of/day_of_assembly.dart';
import '../../features/live/live_repository.dart';
import '../../features/discovery/discovery_assembly.dart';
import '../../features/journey/journey_assembly.dart';
import '../../features/preparation/preparation_assembly.dart';
import '../../features/questionnaires/questionnaire_assembly.dart';
import '../../features/space/space_assembly.dart';
import '../../features/space/space_occurrence_repository.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/location/location_capability.dart';
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
      preferences: preferences,
      config: config,
      interactions: interactions,
      api: api,
    );
  }

  recovery.restoreLaunchLocation(
    await launchPreferences.readShellLocation(profileId),
  );
  final actorContext = await ActorContextController.restore(
    profileId: profileId,
    store: launchPreferences,
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

  return AppRuntime(
    tokens: tokens,
    session: session,
    recovery: recovery,
    launchPreferences: launchPreferences,
    preferences: preferences,
    config: config,
    interactions: interactions,
    api: api,
    database: database,
    store: store,
    personal: personal,
    interoperability: interoperability,
    discovery: buildDiscoveryRepository(
      database: database,
      store: store,
      profileId: profileId,
      api: api,
      sync: sync,
    ),
    location: locationFactory(config),
    accesses: buildAccessRepository(
      database: database,
      store: store,
      profileId: profileId,
      api: api,
      sync: sync,
    ),
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
    space: buildWorkspaceContextRepository(
      database: database,
      store: store,
      profileId: profileId,
      actorContext: actorContext,
      sync: sync,
    ),
    spaceOccurrences: SpaceOccurrenceRepository(
      database: database,
      store: store,
      profileId: profileId,
      sync: sync,
    ),
  );
}
