import 'dart:async';

import 'package:go_router/go_router.dart';

import '../features/auth/account_actions.dart';
import '../features/auth/login_screen.dart';
import '../features/guest/guest_screen.dart';
import '../features/mark/mark_screen.dart';
import '../features/personal/projection_screen.dart';
import '../navigation/refresh_boundary.dart';
import '../navigation/secondary_screen.dart';
import 'app_shell.dart';
import 'providers.dart';

GoRouter createMakoloRouter(
  AppRuntime runtime, {
  required void Function() onAuthenticationChanged,
}) {
  final personal = runtime.personal;
  final initialLocation = runtime.isAuthenticated
      ? runtime.recovery.initialLocation()
      : runtime.recovery.awaitingAuthentication
      ? '/login'
      : '/discover';

  void switchAccount() {
    unawaited(
      endMakoloAccountSession(
        runtime: runtime,
        onAuthenticationChanged: onAuthenticationChanged,
        switchAccount: true,
      ),
    );
  }

  void logout() {
    unawaited(
      endMakoloAccountSession(
        runtime: runtime,
        onAuthenticationChanged: onAuthenticationChanged,
        switchAccount: false,
      ),
    );
  }

  return GoRouter(
    initialLocation: initialLocation,
    redirect: (context, state) {
      if (runtime.isAuthenticated &&
          (state.uri.path == '/login' || state.uri.path == '/create-account')) {
        return '/now';
      }
      return null;
    },
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => AppShell(
          navigationShell: navigationShell,
          recovery: runtime.recovery,
          runtime: runtime,
          onSwitchAccount: runtime.isAuthenticated ? switchAccount : null,
          onLogout: runtime.isAuthenticated ? logout : null,
        ),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/now',
                builder: (context, state) => personal == null
                    ? const GuestPersonalScreen(
                        title: 'Now',
                        message: 'Cette partie devient personnelle lorsque vous vous connectez. Vous pouvez continuer à découvrir Makolo sans compte.',
                      )
                    : MakoloRefreshBoundary(
                        child: ProjectionScreen(
                          title: 'Now',
                          stream: personal.watchNow(),
                          emptyMessage: 'Tout est en ordre. ✓',
                          showTitle: false,
                        ),
                      ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/discover',
                builder: (context, state) => GuestDiscoverScreen(
                  isAuthenticated: runtime.isAuthenticated,
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/ongoing',
                builder: (context, state) => personal == null
                    ? const GuestPersonalScreen(
                        title: 'En cours',
                        message: 'Vos démarches et éléments en cours apparaissent ici après connexion. Découvrir reste disponible sans compte.',
                      )
                    : MakoloRefreshBoundary(
                        child: ProjectionScreen(
                          title: 'En cours',
                          stream: personal.watchOngoing(),
                          emptyMessage: 'Aucun engagement en cours.',
                          showTitle: false,
                        ),
                      ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/me',
                builder: (context, state) => personal == null
                    ? const GuestPersonalScreen(
                        title: 'Moi',
                        message: 'Cette partie rassemble vos informations personnelles. Elle reste protégée tant que vous continuez sans compte.',
                      )
                    : MakoloRefreshBoundary(
                        child: ProjectionScreen(
                          title: 'Moi',
                          stream: personal.watchMe(),
                          emptyMessage:
                              'Aucune information personnelle à afficher.',
                          showTitle: false,
                        ),
                      ),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => LoginScreen(runtime: runtime),
      ),
      GoRoute(
        path: '/create-account',
        builder: (context, state) =>
            LoginScreen(runtime: runtime, startInSignup: true),
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => runtime.isAuthenticated
            ? MarkScreen(runtime: runtime)
            : const GuestPersonalScreen(
                title: 'Connectez-vous pour continuer',
                message: 'Le Makolo Mark devient une action personnelle lorsque vous êtes connecté.',
              ),
      ),
      GoRoute(
        path: '/conversations',
        builder: (context, state) => runtime.isAuthenticated
            ? const MakoloSecondaryScreen(
                title: 'Conversations',
                message: 'Vos conversations auront ici leur destination mobile dédiée.',
              )
            : const GuestPersonalScreen(
                title: 'Connectez-vous pour continuer',
                message: 'Vos conversations sont personnelles et restent protégées sans connexion.',
              ),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => runtime.isAuthenticated
            ? const MakoloSecondaryScreen(
                title: 'Notifications',
                message: 'Rien de nouveau pour le moment.',
              )
            : const GuestPersonalScreen(
                title: 'Connectez-vous pour continuer',
                message: 'Vos notifications sont personnelles et restent protégées sans connexion.',
              ),
      ),
      GoRoute(
        path: '/discover/search',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Rechercher',
          message:
              'Commencez une recherche pour explorer les possibilités Makolo.',
        ),
      ),
      GoRoute(
        path: '/discover/filters',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Filtres',
          message:
              'Aucun filtre supplémentaire n’est nécessaire pour le moment.',
        ),
      ),
      GoRoute(
        path: '/ongoing/calendar',
        builder: (context, state) => runtime.isAuthenticated
            ? const MakoloSecondaryScreen(
                title: 'Calendrier',
                message: 'Aucune date à afficher pour le moment.',
              )
            : const GuestPersonalScreen(
                title: 'Connectez-vous pour continuer',
                message: 'Le calendrier organise vos éléments personnels après connexion.',
              ),
      ),
      for (final prefix in const [
        'journeys',
        'activities',
        'occurrences',
        'accesses',
        'dossiers',
        'projects',
        'groups',
      ])
        GoRoute(
          path: '/$prefix/:id',
          builder: (context, state) {
            runtime.recovery.rememberLocation(state.uri.toString());
            if (!runtime.isAuthenticated) {
              return const GuestPersonalScreen(
                title: 'Connectez-vous pour continuer',
                message: 'Cette destination concerne une activité personnelle. Votre destination reste disponible après reconnexion.',
              );
            }
            return const MakoloSecondaryScreen(
              title: 'Continuer dans Makolo',
              message: 'Rien d’autre à afficher pour le moment.',
            );
          },
        ),
    ],
  );
}
