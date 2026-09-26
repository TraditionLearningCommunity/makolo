import 'package:go_router/go_router.dart';

import '../features/mark/mark_screen.dart';
import '../features/personal/placeholder_screen.dart';
import '../features/personal/projection_screen.dart';
import 'app_shell.dart';
import 'providers.dart';

GoRouter createMakoloRouter(AppRuntime runtime) {
  final personal = runtime.personal!;

  return GoRouter(
    initialLocation: '/now',
    routes: [
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
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
                  'La fondation A1 est prête. L’expérience exploratoire complète arrive dans A2.',
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
          builder: (context, state) => PlaceholderScreen(
            title: 'Continuer dans Makolo',
            message:
                'Cette destination structurée sera revalidée par son domaine propriétaire avant d’exposer une action.',
          ),
        ),
    ],
  );
}
