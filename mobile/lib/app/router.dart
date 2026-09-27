import 'package:go_router/go_router.dart';

import '../features/mark/mark_screen.dart';
import '../features/personal/placeholder_screen.dart';
import '../features/personal/projection_screen.dart';
import '../navigation/refresh_boundary.dart';
import '../navigation/secondary_screen.dart';
import 'app_shell.dart';
import 'providers.dart';

GoRouter createMakoloRouter(
  AppRuntime runtime, {
  void Function()? onAuthenticationChanged,
}) {
  final personal = runtime.personal!;

  return GoRouter(
    initialLocation: runtime.recovery.initialLocation(),
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => AppShell(
          navigationShell: navigationShell,
          recovery: runtime.recovery,
          runtime: runtime,
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
                    message: 'Les possibilités à explorer apparaîtront ici lorsque leur expérience mobile sera prête.',
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
          message: 'La recherche globale sera branchée ici sans simuler de résultats.',
        ),
      ),
      GoRoute(
        path: '/discover/filters',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Filtres',
          message: 'Les filtres de Découvrir seront proposés ici lorsqu’ils auront un contrat consommable.',
        ),
      ),
      GoRoute(
        path: '/ongoing/calendar',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Calendrier',
          message: 'Cette lecture temporelle organisera les dates déjà exposées par En cours.',
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
              message: 'Cette destination sera disponible ici lorsque son expérience mobile sera prête.',
            );
          },
        ),
    ],
  );
}
