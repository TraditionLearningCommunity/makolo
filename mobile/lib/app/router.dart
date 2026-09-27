import 'dart:async';

import 'package:go_router/go_router.dart';

import '../features/auth/account_actions.dart';
import '../features/mark/mark_screen.dart';
import '../features/personal/placeholder_screen.dart';
import '../features/personal/projection_screen.dart';
import '../navigation/refresh_boundary.dart';
import '../navigation/secondary_screen.dart';
import 'app_shell.dart';
import 'providers.dart';

GoRouter createMakoloRouter(
  AppRuntime runtime, {
  required void Function() onAuthenticationChanged,
}) {
  final personal = runtime.personal!;

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
    initialLocation: runtime.recovery.initialLocation(),
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => AppShell(
          navigationShell: navigationShell,
          recovery: runtime.recovery,
          runtime: runtime,
          onSwitchAccount: switchAccount,
          onLogout: logout,
        ),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/now',
                builder: (context, state) => MakoloRefreshBoundary(
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
                builder: (context, state) => const MakoloRefreshBoundary(
                  child: PlaceholderScreen(
                    title: 'Découvrir',
                    message: 'Rien à explorer pour le moment.',
                  ),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/ongoing',
                builder: (context, state) => MakoloRefreshBoundary(
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
                builder: (context, state) => MakoloRefreshBoundary(
                  child: ProjectionScreen(
                    title: 'Moi',
                    stream: personal.watchMe(),
                    emptyMessage: 'Aucune information personnelle à afficher.',
                    showTitle: false,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => MarkScreen(runtime: runtime),
      ),
      GoRoute(
        path: '/conversations',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Conversations',
          message:
              'Vos conversations auront ici leur destination mobile dédiée.',
        ),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Notifications',
          message: 'Les notifications Makolo auront ici leur destination mobile dédiée.',
        ),
      ),
      GoRoute(
        path: '/discover/search',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Rechercher',
          message: 'Commencez une recherche pour explorer les possibilités Makolo.',
        ),
      ),
      GoRoute(
        path: '/discover/filters',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Filtres',
          message: 'Aucun filtre supplémentaire n’est nécessaire pour le moment.',
        ),
      ),
      GoRoute(
        path: '/ongoing/calendar',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Calendrier',
          message: 'Aucune date à afficher pour le moment.',
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
            return const MakoloSecondaryScreen(
              title: 'Continuer dans Makolo',
              message: 'Cette destination n’a rien d’autre à afficher pour le moment.',
            );
          },
        ),
    ],
  );
}
