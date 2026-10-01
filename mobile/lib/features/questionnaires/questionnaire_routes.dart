import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import '../journey/journey_selector.dart';
import 'questionnaire_form_screen.dart';
import 'questionnaire_repository.dart';

List<RouteBase> questionnaireRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/journeys/:journeyId/forms/:requestId',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final form =
          state.extra is JourneyFormSummary ? state.extra! as JourneyFormSummary : null;
      final repository = runtime.questionnaires;
      final drafts = runtime.drafts;
      final outbox = runtime.outbox;
      final submit = runtime.questionnaireSubmit;
      if (form == null ||
          repository == null ||
          drafts == null ||
          outbox == null ||
          submit == null ||
          form.detailLink.isEmpty) {
        return const MakoloSecondaryScreen(
          title: 'Formulaire',
          message: 'Rouvrez ce formulaire depuis la démarche pour reprendre avec les liens du propriétaire.',
        );
      }
      return QuestionnaireFormScreen(
        requestId: state.pathParameters['requestId']!,
        journeyId: state.pathParameters['journeyId']!,
        links: QuestionnaireOwnerLinks(
          detail: form.detailLink,
          save: form.saveLink,
          submit: form.submitLink,
        ),
        repository: repository,
        drafts: drafts,
        outbox: outbox,
        submitCoordinator: submit,
        outboxProcessor: runtime.outboxProcessor,
      );
    },
  ),
];
