import 'package:go_router/go_router.dart';

import '../features/mark/mark_screen.dart';
import '../features/personal/placeholder_screen.dart';
import '../features/personal/projection_screen.dart';
import 'app_shell.dart';
import 'providers.dart';

GoRouter createMakoloRouter(AppRuntime runtime) {
  final personal = runtime.personal!;

  return GoRouter(
    initialLocation: runtime.recovery.initialLocation(),
    routes: [
      ShellRoute(
        builder: (context, state, child) => AppShell(
          recovery: runtime.recovery,
          child: child,
        ),
        routes: [
          GoRoute(
            path: '/now',
            builder: (context, state) => ProjectionScreen(
              title: 'Maintenant',
              stream: personal.watchNow(),
              emptyMessage: 'Tout est en ordre. ✓',
            ),
          ),
          GoRoute(
            path: '/discover',
            builder: (context, state) => const PlaceholderScreen(
              title: 'Découvrir',
              message:
                  'De nouvelles possibilités apparaîtront ici lorsqu’elles seront disponibles.',
            ),
          ),
          GoRoute(
            path: '/ongoing',
            builder: (context, state) => ProjectionScreen(
              title: 'En cours',
              stream: personal.watchOngoing(),
              emptyMessage: 'Aucun engagement en cours.',
            ),
          ),
          GoRoute(
            path: '/me',
            builder: (context, state) => ProjectionScreen(
              title: 'Moi',
              stream: personal.watchMe(),
              emptyMessage: 'Aucune information personnelle à afficher.',
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => const MarkScreen(),
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
            return const PlaceholderScreen(
              title: 'Continuer dans Makolo',
              message:
                  'Cette destination sera disponible ici lorsque son expérience mobile sera prête.',
            );
          },
        ),
    ],
  );
}
