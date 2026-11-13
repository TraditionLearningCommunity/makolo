import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import '../questionnaires/questionnaire_form_screen.dart';
import '../questionnaires/questionnaire_repository.dart';
import 'conversation_context_screen.dart';
import 'conversation_screens.dart';
import 'conversation_details_screen.dart';
import 'conversation_history_screen.dart';
import 'history_screen.dart';
import '../me/me_support_screen.dart';
import 'dossier_workspace_screen.dart';
import 'dossier_people_screen.dart';
import 'project_workspace_screen.dart';

List<RouteBase> continuityRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/appuis',
    builder: (context, state) => runtime.api == null || runtime.store == null
        ? const MakoloSecondaryScreen(
            title: 'Appuis',
            message: 'Les appuis sont momentanément indisponibles.',
          )
        : MeSupportScreen(runtime: runtime),
  ),
  GoRoute(
    path: '/conversations',
    builder: (context, state) {
      final repository = runtime.conversations;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Conversations',
          message: 'Aucune conversation à afficher pour le moment.',
        );
      }
      final actor = runtime.actorContext?.value;
      final requestedContext = state.uri.queryParameters['context'];
      final requestedSpace = state.uri.queryParameters['space'];
      // A stale, forged or foreign Space link never falls back to the
      // personal inbox. Current actor authorization is rechecked server-side.
      if (requestedContext != null &&
          (requestedContext != 'space' ||
              actor is! SpaceActorContext ||
              requestedSpace != actor.space.id)) {
        return const MakoloSecondaryScreen(
          title: 'Conversations',
          message: 'Ce contexte de conversations n’est plus disponible.',
        );
      }
      final spaceId = actor is SpaceActorContext ? actor.space.id : null;
      return ConversationListScreen(
        key: ValueKey('conversation-list-${spaceId ?? 'personal'}'),
        spaceId: spaceId,
        repository: repository,
        onOpen: (id) => context.push('/conversations/$id'),
        onOpenPoint: (id, pointId) => context.push(
          '/conversations/$id?focus=${Uri.encodeQueryComponent(pointId)}',
        ),
      );
    },
  ),
  GoRoute(
    path: '/conversations/:id/history',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.conversations;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Historique',
          message: 'Cette conversation n’est pas disponible sur cet appareil.',
        );
      }
      final conversationId = state.pathParameters['id']!;
      return ConversationHistoryScreen(
        repository: repository,
        conversationId: conversationId,
        initialQuery: state.uri.queryParameters['q'] ?? '',
        initialSection: state.uri.queryParameters['section'] ?? 'history',
        onOpenPoint: (pointId) => context.push(
          '/conversations/$conversationId?focus=${Uri.encodeQueryComponent(pointId)}',
        ),
      );
    },
  ),
  GoRoute(
    path: '/conversations/:id/details',
    builder: (context, state) {
      final repository = runtime.conversations;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Conversation',
          message: 'Détails indisponibles sur cet appareil.',
        );
      }
      final id = state.pathParameters['id']!;
      return ConversationDetailsScreen(
        repository: repository,
        conversationId: id,
        onOpenHistory: () => context.push('/conversations/$id/history'),
        onOpenConversation: () => context.pop(),
        onOpenSubject: (route) => context.push(route),
      );
    },
  ),
  GoRoute(
    path: '/conversations/:id',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.conversations;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Conversation',
          message: 'Cette conversation n’est pas disponible sur cet appareil.',
        );
      }
      final actor = runtime.actorContext?.value;
      return ConversationDetailScreen(
        id: state.pathParameters['id']!,
        repository: repository,
        representedSpaceId: actor is SpaceActorContext ? actor.space.id : null,
        focusPointId: state.uri.queryParameters['focus'],
        onOpenDetails: () => context.push(
          '/conversations/${state.pathParameters['id']}/details',
        ),
        onOpenHistory: () => context.push(
          '/conversations/${state.pathParameters['id']}/history',
        ),
        onOpenRelatedPoint: (pointId) => context.push(
          '/conversations/${state.pathParameters['id']}?focus=${Uri.encodeQueryComponent(pointId)}',
        ),
        onOpenFormRequest: (requestId) async {
          await context.push(
            '/conversations/${state.pathParameters['id']}/forms/$requestId',
          );
          if (context.mounted) {
            try {
              await repository.refreshDetail(state.pathParameters['id']!);
            } on Object {
              // Existing local Conversation projection remains available.
            }
          }
        },
      );
    },
  ),
  GoRoute(
    path: '/conversations/:id/forms/:requestId',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.questionnaires;
      final drafts = runtime.drafts;
      final outbox = runtime.outbox;
      final submit = runtime.questionnaireSubmit;
      if (repository == null ||
          drafts == null ||
          outbox == null ||
          submit == null) {
        return const MakoloSecondaryScreen(
          title: 'Formulaire',
          message: 'Formulaire indisponible sur cet appareil.',
        );
      }
      final requestId = state.pathParameters['requestId']!;
      final base = 'api/v1/questionnaires/requests/$requestId/';
      return QuestionnaireFormScreen(
        requestId: requestId,
        journeyId: '',
        links: QuestionnaireOwnerLinks(
          detail: base,
          save: '${base}save/',
          submit: '${base}submit/',
        ),
        repository: repository,
        drafts: drafts,
        outbox: outbox,
        submitCoordinator: submit,
        outboxProcessor: runtime.outboxProcessor,
      );
    },
  ),
  GoRoute(
    path: '/conversations/by-context/:kind/:id',
    builder: (context, state) {
      final repository = runtime.conversations;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Conversations',
          message: 'Aucune conversation disponible sur cet appareil.',
        );
      }
      return ConversationContextScreen(
        repository: repository,
        kind: state.pathParameters['kind']!,
        contextId: state.pathParameters['id']!,
        onOpen: (id) => context.pushReplacement('/conversations/$id'),
      );
    },
  ),
  GoRoute(
    path: '/history',
    builder: (context, state) {
      final repository = runtime.history;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Historique',
          message: 'Aucun historique à afficher pour le moment.',
        );
      }
      return HistoryScreen(
        repository: repository,
        onOpenResource: (kind, id) {
          if (kind == 'journey') {
            context.push('/journeys/$id');
          } else if (kind == 'access') {
            context.push('/accesses/$id');
          }
        },
      );
    },
  ),
  GoRoute(
    path: '/dossiers/:id/people',
    builder: (context, state) {
      final repository = runtime.objectives;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Personnes et responsabilités',
          message: 'Ce Dossier n’est pas disponible sur cet appareil.',
        );
      }
      return DossierPeopleScreen(
        id: state.pathParameters['id']!,
        repository: repository,
        actorContext: runtime.actorContext,
        onOpenPerson: (id) =>
            context.push('/people/${Uri.encodeComponent(id)}'),
        onOpenMyPassport: () => context.push('/me/passport'),
      );
    },
  ),
  GoRoute(
    path: '/dossiers/:id',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.objectives;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Dossier',
          message: 'Ce dossier n’est pas disponible sur cet appareil.',
        );
      }
      return DossierWorkspaceScreen(
        id: state.pathParameters['id']!,
        repository: repository,
        actorContext: runtime.actorContext,
        sourceProjectId: state.uri.queryParameters['from_project'],
        onReturnToProject: () {
          if (context.canPop()) {
            context.pop();
          } else {
            final fromProject = state.uri.queryParameters['from_project'];
            if (fromProject != null) {
              context.push('/projects/${Uri.encodeComponent(fromProject)}');
            }
          }
        },
        api: runtime.api,
        conversations: runtime.conversations,
        onOpenConversation: (id) => context.push('/conversations/$id'),
        onOpenProject: (id) => context.push('/projects/$id'),
        onOpenOwnerSpace: (slug) =>
            context.push('/spaces/${Uri.encodeComponent(slug)}'),
        onOpenPerson: (id) =>
            context.push('/people/${Uri.encodeComponent(id)}'),
        onOpenMyPassport: () => context.push('/me/passport'),
        onOpenPeople: () => context.push(
          '/dossiers/${Uri.encodeComponent(state.pathParameters['id']!)}/people',
        ),
        onOpenJourney: (id) => context.push('/journeys/$id'),
      );
    },
  ),
  GoRoute(
    path: '/projects/:id',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.objectives;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Projet',
          message: 'Ce projet n’est pas disponible sur cet appareil.',
        );
      }
      return ProjectWorkspaceScreen(
        id: state.pathParameters['id']!,
        repository: repository,
        actorContext: runtime.actorContext,
        api: runtime.api,
        conversations: runtime.conversations,
        onOpenConversation: (id) => context.push('/conversations/$id'),
        onOpenDossier: (id) => context.push(
          '/dossiers/$id?from_project=${state.pathParameters['id']}',
        ),
        onOpenPerson: (id) =>
            context.push('/people/${Uri.encodeComponent(id)}'),
        onOpenMyPassport: () => context.push('/me/passport'),
      );
    },
  ),
];
