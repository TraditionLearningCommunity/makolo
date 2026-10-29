import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import '../resources/resource_detail_screen.dart';
import '../resources/resources_screen.dart';
import 'me_screen.dart';
import 'me_passport_screen.dart';
import 'me_profile_screen.dart';
import 'me_saved_screen.dart';
import 'me_considerations_screen.dart';

StatefulShellBranch meBranch(AppRuntime runtime) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: '/me',
      builder: (context, state) => MeScreen(
        repository: runtime.personal!,
        api: runtime.api,
        onOpenDestination: (destination) {
          if (destination.kind == 'history') {
            context.push('/history');
            return true;
          }
          if (destination.kind == 'considerations') {
            context.push('/me/considerations');
            return true;
          }
          if (destination.kind == 'saved_collection') {
            context.push('/me/saved');
            return true;
          }
          if (destination.kind == 'avatar_edit') {
            context.push('/me/profile?avatar=1');
            return true;
          }
          if (destination.kind == 'profile_self') {
            context.push('/me/profile');
            return true;
          }
          if (destination.kind == 'passport') {
            context.push('/me/passport');
            return true;
          }
          if (destination.kind == 'activity') {
            context.push('/activities/${destination.id}');
            return true;
          }
          if (destination.kind == 'group') {
            context.push('/groups/${destination.id}');
            return true;
          }
          if (destination.kind == 'watch') {
            context.push('/discover/watches/${destination.id}');
            return true;
          }
          if (destination.kind == 'profile') {
            context.push('/people/${destination.id}');
            return true;
          }
          if (destination.kind == 'space' && destination.link != null) {
            context.push('/spaces/${Uri.encodeComponent(destination.link!)}');
            return true;
          }
          if (destination.kind == 'access_collection') {
            context.push('/accesses');
            return true;
          }
          if (destination.kind == 'resource_collection') {
            context.push('/me/resources');
            return true;
          }
          if (destination.kind == 'personal_asset') {
            context.push('/me/resources/${destination.id}');
            return true;
          }
          return false;
        },
      ),
      routes: [
        GoRoute(
          path: 'considerations',
          builder: (context, state) => runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Ce qui compte pour moi',
                  message: 'Préférences momentanément indisponibles.',
                )
              : MeConsiderationsScreen(
                  api: runtime.api!, personal: runtime.personal!,
                  onSaved: () => context.push('/me/saved'),
                  onWatches: () => context.push('/discover/watches'),
                ),
        ),
        GoRoute(
          path: 'saved',
          builder: (context, state) => runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes enregistrements',
                  message: 'Enregistrements momentanément indisponibles.',
                )
              : MeSavedScreen(
                  api: runtime.api!, personal: runtime.personal!,
                  onOpen: (id) => context.push('/activities/$id'),
                  onDiscover: () => context.go('/discover'),
                ),
        ),
        GoRoute(
          path: 'profile',
          builder: (context, state) =>
              runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Modifier mon passeport',
                  message: 'Profil momentanément indisponible.',
                )
              : MeProfileScreen(
                  api: runtime.api!, personal: runtime.personal!,
                  openAvatarPicker: state.uri.queryParameters['avatar'] == '1',
                ),
        ),
        GoRoute(
          path: 'passport',
          builder: (context, state) => runtime.api == null
              ? const MakoloSecondaryScreen(
                  title: 'Passeport Makolo',
                  message: 'Passeport momentanément indisponible.',
                )
              : MePassportScreen(
                  api: runtime.api!,
                  personal: runtime.personal,
                  onEdit: runtime.personal == null
                      ? null
                      : () => context.push('/me/profile'),
                ),
        ),
        GoRoute(
          path: 'resources',
          builder: (context, state) {
            final repository = runtime.resources;
            if (repository == null) {
              return const MakoloSecondaryScreen(
                title: 'Mes ressources',
                message:
                    'Vos ressources ne sont pas disponibles sur cet appareil.',
              );
            }
            return ResourcesScreen(
              repository: repository,
              onOpenResource: (id) => context.push('/me/resources/$id'),
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
                  onOpenJourney: (id) => context.push('/journeys/$id'),
                );
              },
            ),
          ],
        ),
      ],
    ),
  ],
);
