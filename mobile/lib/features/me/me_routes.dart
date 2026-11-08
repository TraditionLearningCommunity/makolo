import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import '../resources/resource_detail_screen.dart';
import '../resources/resources_screen.dart';
import '../continuity/objective_collection_screen.dart';
import '../continuity/objective_organizer_screen.dart';
import '../continuity/objective_create_screen.dart';
import '../continuity/objective_repository.dart';
import 'me_screen.dart';
import 'me_passport_screen.dart';
import 'me_profile_screen.dart';
import 'me_saved_screen.dart';
import 'me_considerations_screen.dart';
import 'me_collectives_screen.dart';
import 'me_follows_screen.dart';
import 'me_support_screen.dart';

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
          if (destination.kind == 'organizer_collection') {
            context.push('/me/demarches');
            return true;
          }
          if (destination.kind == 'project_collection') {
            context.push('/me/projects');
            return true;
          }
          if (destination.kind == 'dossier_collection') {
            context.push('/me/dossiers');
            return true;
          }
          if (destination.kind == 'watches_collection') {
            context.push('/discover/watches');
            return true;
          }
          if (destination.kind == 'follows_collection') {
            context.push('/me/follows');
            return true;
          }
          if (destination.kind == 'support_collection') {
            context.push('/me/support');
            return true;
          }
          if (destination.kind == 'considerations') {
            context.push('/me/considerations');
            return true;
          }
          if (destination.kind == 'collectives') {
            context.push('/me/collectives');
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
          if (destination.kind == 'access') {
            context.push('/accesses/${destination.id}');
            return true;
          }
          if (destination.kind == 'journey') {
            context.push('/journeys/${destination.id}');
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
          path: 'demarches',
          builder: (context, state) => runtime.objectives == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes démarches',
                  message: 'Vos démarches ne sont pas encore disponibles sur cet appareil.',
                )
              : ObjectiveOrganizerScreen(
                  repository: runtime.objectives!,
                  onOpenItem: (kind, id) {
                    if (kind == 'project') {
                      context.push('/projects/$id');
                    } else if (kind == 'dossier') {
                      context.push('/dossiers/$id');
                    } else if (kind == 'journey') {
                      context.push('/journeys/$id');
                    }
                  },
                  onCreate: (kind) =>
                      context.push('/me/demarches/new?kind=$kind'),
                ),
          routes: [
            GoRoute(
              path: 'new',
              builder: (context, state) {
                final kind = state.uri.queryParameters['kind'];
                if (runtime.objectives == null ||
                    runtime.api == null ||
                    (kind != 'project' && kind != 'dossier')) {
                  return const MakoloSecondaryScreen(
                    title: 'Créer',
                    message: 'Création momentanément indisponible.',
                  );
                }
                return ObjectiveCreateScreen(
                  kind: kind!,
                  repository: runtime.objectives!,
                  api: runtime.api!,
                  onCreated: (id) => context.pushReplacement(
                    kind == 'project' ? '/projects/$id' : '/dossiers/$id',
                  ),
                );
              },
            ),
          ],
        ),
        GoRoute(
          path: 'projects',
          builder: (context, state) => runtime.objectives == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes projets',
                  message: 'Mes projets sont momentanément indisponibles.',
                )
              : ObjectiveCollectionScreen(
                  kind: ObjectiveDepth.project,
                  repository: runtime.objectives!,
                  onOpenItem: (id) => context.push('/projects/$id'),
                ),
        ),
        GoRoute(
          path: 'dossiers',
          builder: (context, state) => runtime.objectives == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes dossiers',
                  message: 'Mes dossiers sont momentanément indisponibles.',
                )
              : ObjectiveCollectionScreen(
                  kind: ObjectiveDepth.dossier,
                  repository: runtime.objectives!,
                  onOpenItem: (id) => context.push('/dossiers/$id'),
                ),
        ),
        GoRoute(
          path: 'follows',
          builder: (context, state) =>
              runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes suivis',
                  message: 'Mes suivis sont momentanément indisponibles.',
                )
              : MeFollowsScreen(
                  api: runtime.api!,
                  personal: runtime.personal!,
                  onOpenDestination: (destination) {
                    if (destination.kind == 'profile') {
                      context.push('/people/${destination.id}');
                      return true;
                    }
                    if (destination.kind == 'space' &&
                        destination.link != null) {
                      context.push(
                        '/spaces/${Uri.encodeComponent(destination.link!)}',
                      );
                      return true;
                    }
                    return false;
                  },
                ),
        ),
        GoRoute(
          path: 'support',
          builder: (context, state) => runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes appuis',
                  message: 'Mes appuis sont momentanément indisponibles.',
                )
              : MeSupportScreen(personal: runtime.personal!),
        ),
        GoRoute(
          path: 'collectives',
          builder: (context, state) =>
              runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes collectifs',
                  message: 'Mes collectifs sont momentanément indisponibles.',
                )
              : MeCollectivesScreen(
                  api: runtime.api!,
                  personal: runtime.personal!,
                  onOpenDestination: (destination) {
                    if (destination.kind == 'group') {
                      context.push('/groups/${destination.id}');
                      return true;
                    }
                    if (destination.kind == 'space' &&
                        destination.link != null) {
                      context.push(
                        '/spaces/${Uri.encodeComponent(destination.link!)}',
                      );
                      return true;
                    }
                    return false;
                  },
                ),
        ),
        GoRoute(
          path: 'considerations',
          builder: (context, state) =>
              runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Ce qui compte pour moi',
                  message: 'Préférences momentanément indisponibles.',
                )
              : MeConsiderationsScreen(
                  api: runtime.api!,
                  personal: runtime.personal!,
                  sync: runtime.sync,
                ),
        ),
        GoRoute(
          path: 'saved',
          builder: (context, state) =>
              runtime.api == null || runtime.personal == null
              ? const MakoloSecondaryScreen(
                  title: 'Mes enregistrements',
                  message: 'Enregistrements momentanément indisponibles.',
                )
              : MeSavedScreen(
                  api: runtime.api!,
                  personal: runtime.personal!,
                  sync: runtime.sync,
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
                  api: runtime.api!,
                  personal: runtime.personal!,
                  sync: runtime.sync,
                  drafts: runtime.drafts,
                  openAvatarPicker: state.uri.queryParameters['avatar'] == '1',
                  focusVisibility:
                      state.uri.queryParameters['visibility'] == '1',
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
                      : () async {
                          await context.push('/me/profile');
                        },
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
