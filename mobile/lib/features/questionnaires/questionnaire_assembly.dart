import '../../auth/token_store.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/outbox/outbox_processor.dart';
import '../../sync/outbox/outbox_repository.dart';
import '../journey/journey_repository.dart';
import 'questionnaire_repository.dart';
import 'questionnaire_submit_coordinator.dart';

class QuestionnaireAssembly {
  const QuestionnaireAssembly({
    required this.repository,
    required this.submit,
    required this.outboxProcessor,
  });

  final QuestionnaireRepository repository;
  final QuestionnaireSubmitCoordinator? submit;
  final OutboxProcessor? outboxProcessor;
}

QuestionnaireAssembly buildQuestionnaireAssembly({
  required MakoloDatabase database,
  required ProfileStore store,
  required String profileId,
  required MakoloApiClient? api,
  required TokenStore tokens,
  required OutboxRepository outbox,
  required DraftRepository drafts,
  required JourneyRepository journeys,
}) {
  final repository = QuestionnaireRepository(
    database: database,
    store: store,
    profileId: profileId,
    sync: null,
  );
  if (api == null) {
    return QuestionnaireAssembly(
      repository: repository,
      submit: null,
      outboxProcessor: null,
    );
  }
  final submit = QuestionnaireSubmitCoordinator(
    api: api,
    tokens: tokens,
    outbox: outbox,
    drafts: drafts,
    questionnaires: repository,
    journeys: journeys,
  );
  return QuestionnaireAssembly(
    repository: repository,
    submit: submit,
    outboxProcessor: OutboxProcessor(
      repository: outbox,
      handlers: {
        QuestionnaireSubmitCoordinator.operationKind: submit.handler,
      },
      reconcilers: {
        QuestionnaireSubmitCoordinator.operationKind: submit.reconciler,
      },
    ),
  );
}
