import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'journey_detail_screen.dart';
import 'journey_artifact_screen.dart';
import 'journey_requirement_evidence_screen.dart';
import 'space_beneficiary_journey_screen.dart';
import 'space_beneficiary_resources_screen.dart';
import 'space_beneficiary_journeys_screen.dart';
import '../questionnaires/questionnaire_form_screen.dart';
import '../questionnaires/questionnaire_repository.dart';

String? _ownerResourceId(String link, String collection) {
  final uri = Uri.tryParse(link);
  if (uri == null) return null;
  final segments = uri.pathSegments;
  final index = segments.indexOf(collection);
  if (index < 0 || index + 1 >= segments.length) return null;
  final id = segments[index + 1].trim();
  return id.isEmpty ? null : id;
}

SpaceActorIdentity? _activeSpace(AppRuntime runtime, String slug) {
  final actor = runtime.actorContext?.value;
  if (actor is! SpaceActorContext || actor.space.slug != slug) return null;
  return actor.space;
}

List<RouteBase> journeyRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/journeys/:id/requirements/:assessmentId/evidence',
    builder: (context, state) {
      if (runtime.database == null || runtime.store == null ||
          runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Preuve',
          message: 'Cette démarche privée n’est pas disponible sur cet appareil.',
        );
      }
      return JourneyRequirementEvidenceScreen(
        key: ValueKey('profile-evidence:${runtime.session!.profileId}:${state.pathParameters['assessmentId']}'),
        runtime: runtime,
        journeyId: state.pathParameters['id']!,
        assessmentId: state.pathParameters['assessmentId']!,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id/requirements/:assessmentId/evidence',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null || runtime.database == null ||
          runtime.store == null || runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Proposer une preuve',
          message: 'Sélectionnez cet Espace pour poursuivre.',
        );
      }
      return JourneyRequirementEvidenceScreen(
        key: ValueKey('space-evidence:${runtime.session!.profileId}:${space.id}:${state.pathParameters['assessmentId']}'),
        runtime: runtime,
        space: space,
        journeyId: state.pathParameters['id']!,
        assessmentId: state.pathParameters['assessmentId']!,
      );
    },
  ),
  GoRoute(
    path: '/journeys/:id/artifacts',
    builder: (context, state) {
      if (runtime.database == null ||
          runtime.store == null ||
          runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Pièces',
          message:
              'Les pièces privées ne sont pas disponibles sur cet appareil.',
        );
      }
      return JourneyArtifactScreen(
        key: ValueKey(
          'profile-pieces:${runtime.session!.profileId}:${state.pathParameters['id']}',
        ),
        runtime: runtime,
        journeyId: state.pathParameters['id']!,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null ||
          runtime.database == null ||
          runtime.store == null ||
          runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Demandes de cet Espace',
          message: 'Sélectionnez cet Espace pour reprendre ses demandes.',
        );
      }
      return SpaceBeneficiaryJourneysScreen(
        key: ValueKey(
          'space-journey-list:${runtime.session!.profileId}:${space.id}',
        ),
        runtime: runtime,
        space: space,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null ||
          runtime.database == null ||
          runtime.store == null ||
          runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Demande de cet Espace',
          message: 'Sélectionnez cet Espace pour retrouver sa demande.',
        );
      }
      return SpaceBeneficiaryJourneyScreen(
        key: ValueKey(
          'space-journey:${runtime.session!.profileId}:${space.id}:${state.pathParameters['id']}',
        ),
        runtime: runtime,
        space: space,
        journeyId: state.pathParameters['id']!,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id/intake',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null || runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Questions de la demande',
          message: 'Sélectionnez cet Espace pour reprendre ses réponses.',
        );
      }
      return SpaceBeneficiaryIntakeScreen(
        key: ValueKey(
          'space-intake:${runtime.session!.profileId}:${space.id}:${state.pathParameters['id']}',
        ),
        runtime: runtime,
        space: space,
        journeyId: state.pathParameters['id']!,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id/artifacts',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null ||
          runtime.database == null ||
          runtime.store == null ||
          runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Pièces du dossier',
          message: 'Sélectionnez cet Espace pour consulter ses pièces.',
        );
      }
      return JourneyArtifactScreen(
        key: ValueKey(
          'space-pieces:${runtime.session!.profileId}:${space.id}:${state.pathParameters['id']}',
        ),
        runtime: runtime,
        space: space,
        journeyId: state.pathParameters['id']!,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id/resources',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null ||
          runtime.database == null ||
          runtime.store == null ||
          runtime.session == null) {
        return const MakoloSecondaryScreen(
          title: 'Ressources',
          message: 'Sélectionnez cet Espace pour retrouver ses ressources.',
        );
      }
      return SpaceBeneficiaryResourcesScreen(
        key: ValueKey(
          'space-preparation:${runtime.session!.profileId}:${space.id}:${state.pathParameters['id']}',
        ),
        runtime: runtime,
        space: space,
        journeyId: state.pathParameters['id']!,
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id/forms/:requestId',
    builder: (context, state) {
      final slug = state.pathParameters['slug']!;
      final space = _activeSpace(runtime, slug);
      final owner = state.extra;
      final form = owner is Map ? owner : null;
      final links = form?['links'];
      final routes = links is Map ? links : null;
      final detail = routes?['detail'];
      if (space == null ||
          form?['id'] != state.pathParameters['requestId'] ||
          detail is! String ||
          runtime.questionnaires == null ||
          runtime.drafts == null ||
          runtime.outbox == null ||
          runtime.questionnaireSubmit == null ||
          runtime.actorContext == null) {
        return const MakoloSecondaryScreen(
          title: 'Formulaire',
          message: 'Sélectionnez cet Espace et rouvrez le formulaire depuis sa démarche.',
        );
      }
      // Changing the selected Space hides retained private answers immediately.
      return ListenableBuilder(
        listenable: runtime.actorContext!,
        builder: (context, child) {
          if (_activeSpace(runtime, slug) != space) {
            return const MakoloSecondaryScreen(
              title: 'Formulaire',
              message: 'Cet Espace n’est plus sélectionné.',
            );
          }
          return QuestionnaireFormScreen(
            key: ValueKey(
              'space-form:${runtime.session?.profileId}:${space.id}:${form!['id']}',
            ),
            requestId: state.pathParameters['requestId']!,
            journeyId: state.pathParameters['id']!,
            links: QuestionnaireOwnerLinks(
              detail: detail,
              save: routes?['save'] is String
                  ? routes!['save'] as String
                  : null,
              submit: routes?['submit'] is String
                  ? routes!['submit'] as String
                  : null,
            ),
            repository: runtime.questionnaires!,
            drafts: runtime.drafts!,
            outbox: runtime.outbox!,
            submitCoordinator: runtime.questionnaireSubmit!,
            outboxProcessor: runtime.outboxProcessor,
          );
        },
      );
    },
  ),
  GoRoute(
    path: '/space/:slug/beneficiary/journeys/:id/requirements/:assessmentId',
    builder: (context, state) {
      final space = _activeSpace(runtime, state.pathParameters['slug']!);
      if (space == null) {
        return const MakoloSecondaryScreen(
          title: 'Condition',
          message: 'Sélectionnez cet Espace pour voir cette condition.',
        );
      }
      return SpaceBeneficiaryRequirementScreen(
        runtime: runtime,
        space: space,
        journeyId: state.pathParameters['id']!,
        assessmentId: state.pathParameters['assessmentId']!,
      );
    },
  ),
  GoRoute(
    path: '/journeys/:id',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.journeys;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Démarche',
          message: 'Cette démarche n’est pas disponible sur cet appareil.',
        );
      }
      final journeyId = state.pathParameters['id']!;
      return JourneyDetailScreen(
        journeyId: journeyId,
        repository: repository,
        api: runtime.api,
        resourcesRepository: runtime.preparationResources,
        onOpenArtifacts: () => context.push('/journeys/$journeyId/artifacts'),
        onOpenPaymentObligation: (id) =>
            context.push('/payments/obligations/${Uri.encodeComponent(id)}'),
        onOpenCommerceOrder: (id) =>
            context.push('/commerce/orders/${Uri.encodeComponent(id)}'),
        conversations: runtime.conversations,
        onOpenConversation: (id) => context.push('/conversations/$id'),
        onOpenForm: (form) =>
            context.push('/journeys/$journeyId/forms/${form.id}', extra: form),
        onOpenRequirement: (requirement) => context.push(
          '/journeys/$journeyId/requirements/${requirement.id}',
          extra: requirement,
        ),
        onOpenResources: (resourcesLink) => context.push(
          '/journeys/$journeyId/resources',
          extra: resourcesLink,
        ),
        onOpenActivity: (activity) {
          if (activity.link == null || activity.id.isEmpty) return;
          context.push('/activities/${activity.id}');
        },
        onOpenOccurrence: (occurrence) {
          if (occurrence.link == null || occurrence.id.isEmpty) return;
          context.push('/occurrences/${occurrence.id}');
        },
        onOpenAccess: (access) {
          if (access.link == null || access.id.isEmpty) return;
          context.push('/accesses/${access.id}');
        },
        onOpenDayOf: (dayOfLink) {
          final occurrenceId = _ownerResourceId(dayOfLink, 'occurrences');
          if (occurrenceId != null) {
            context.push('/occurrences/$occurrenceId/day-of');
          }
        },
        onOpenLive: (liveLink) {
          final occurrenceId = _ownerResourceId(liveLink, 'occurrences');
          if (occurrenceId != null) {
            context.push('/occurrences/$occurrenceId/live');
          }
        },
      );
    },
  ),
];
