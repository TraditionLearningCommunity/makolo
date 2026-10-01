import '../../auth/token_store.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../features/access/access_repository.dart';
import '../../features/continuity/conversation_repository.dart';
import '../../features/continuity/history_repository.dart';
import '../../features/continuity/objective_repository.dart';
import '../../features/day_of/day_of_repository.dart';
import '../../features/discovery/discovery_repository.dart';
import '../../features/journey/journey_repository.dart';
import '../../features/preparation/preparation_repository.dart';
import '../../features/questionnaires/questionnaire_repository.dart';
import '../../features/questionnaires/questionnaire_submit_coordinator.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/location/location_capability.dart';
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

class AppRuntime {
  AppRuntime({
    required this.tokens,
    required this.session,
    required this.recovery,
    this.launchPreferences,
    this.preferences,
    this.config,
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
  final AppPreferencesController? preferences;
  final MakoloRuntimeConfig? config;
  final ResumableInteractionStore? interactions;

  MakoloMapsConfig get mapConfig =>
      config?.maps ?? const MakoloMapsConfig(enabled: false, style: null);

  bool get isDevelopment => config?.environment == MakoloRuntimeEnvironment.dev;
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
    preferences?.dispose();
    await database?.close();
  }
}
