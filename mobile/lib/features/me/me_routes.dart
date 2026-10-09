import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import '../resources/resource_detail_screen.dart';
import '../resources/resources_screen.dart';
import 'me_screen.dart';

StatefulShellBranch meBranch(AppRuntime runtime) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: '/me',
      builder: (context, state) => MeScreen(
        repository: runtime.personal!,
        onOpenDestination: (destination) {
          if (destination.kind == 'access_collection') {
            context.push('/accesses');
            return true;
          }
          if (destination.kind == 'resource_collection') {
            context.push('/me/resources');
            return true;
          }
          if (destination.kind == 'personal_asset') {
            context.push('/me/resources/' + destination.id);
            return true;
          }
          return false;
        },
      ),
      routes: [
        GoRoute(
          path: 'resources',
          builder: (context, state) {
            final repository = runtime.resources;
            if (repository == null) {
              return const MakoloSecondaryScreen(
                title: 'Mes ressources',
                message: 'Vos ressources ne sont pas disponibles sur cet appareil.',
              );
            }
            return ResourcesScreen(
              repository: repository,
              onOpenResource: (id) => context.push('/me/resources/' + id),
            );
          },
          routes: [
            GoRoute(
              path: ':id',
              builder: (context, state) {
                final repository = runtime.resources;
                final personal = runtime.personal;
                if (repository == null || personal == null) {
                  return const MakoloSecondaryScreen(
                    title: 'Ressource',
                    message: 'Cette ressource n’est pas disponible sur cet appareil.',
                  );
                }
                return ResourceDetailScreen(
                  assetId: state.pathParameters['id']!,
                  repository: repository,
                  personal: personal,
                  onOpenJourney: (id) => context.push('/journeys/' + id),
                );
              },
            ),
          ],
        ),
      ],
    ),
  ],
);
