import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'conversation_screens.dart';
import 'history_screen.dart';
import 'objective_repository.dart';
import 'objective_screen.dart';

List<RouteBase> continuityRoutes(AppRuntime runtime) => [
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
      return ConversationListScreen(
        repository: repository,
        onOpen: (id) => context.push('/conversations/' + id),
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
      return ConversationDetailScreen(
        id: state.pathParameters['id']!,
        repository: repository,
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
            context.push('/journeys/' + id);
          } else if (kind == 'access') {
            context.push('/accesses/' + id);
          }
        },
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
      return ObjectiveDetailScreen(
        kind: ObjectiveDepth.dossier,
        id: state.pathParameters['id']!,
        repository: repository,
        onOpenDossier: (id) => context.push('/dossiers/' + id),
        onOpenJourney: (id) => context.push('/journeys/' + id),
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
      return ObjectiveDetailScreen(
        kind: ObjectiveDepth.project,
        id: state.pathParameters['id']!,
        repository: repository,
        onOpenDossier: (id) => context.push('/dossiers/' + id),
        onOpenJourney: (id) => context.push('/journeys/' + id),
      );
    },
  ),
];
