import 'package:go_router/go_router.dart';

import '../features/auth/login_screen.dart';
import '../features/auth/register_screen.dart';
import '../features/guest/guest_screen.dart';
import '../features/mark/mark_screen.dart';
import '../features/personal/placeholder_screen.dart';
import '../features/personal/projection_screen.dart';
import 'app_shell.dart';
import 'providers.dart';

GoRouter createMakoloRouter(AppRuntime runtime) {
  final personal = runtime.personal;
  final initialLocation = runtime.isAuthenticated
      ? runtime.recovery.initialLocation()
      : runtime.recovery.awaitingAuthentication
      ? '/login'
      : '/discover';

  return GoRouter(
    initialLocation: initialLocation,
    redirect: (context, state) {
      if (runtime.isAuthenticated &&
          (state.uri.path == '/login' ||
              state.uri.path == '/create-account')) {
        return '/now';
      }
      return null;
    },
    routes: [
      ShellRoute(
        builder: (context, state, child) =>
            AppShell(recovery: runtime.recovery, child: child),
        routes: [
          GoRoute(
            path: '/now',
            builder: (context, state) => personal == null
                ? const GuestPersonalScreen(
                    title: 'Maintenant',
                    message:
                        'Cette partie devient personnelle lorsque vous vous connectez. Vous pouvez continuer à découvrir Makolo sans compte.',
                  )
                : ProjectionScreen(
                    title: 'Maintenant',
                    stream: personal.watchNow(),
                    emptyMessage: 'Tout est en ordre. ✓',
                  ),
          ),
          GoRoute(
            path: '/discover',
            builder: (context, state) => GuestDiscoverScreen(
              isAuthenticated: runtime.isAuthenticated,
            ),
          ),
          GoRoute(
            path: '/ongoing',
            builder: (context, state) => personal == null
                ? const GuestPersonalScreen(
                    title: 'En cours',
                    message:
                        'Vos démarches et éléments en cours apparaissent ici après connexion. Découvrir reste disponible sans compte.',
                  )
                : ProjectionScreen(
                    title: 'En cours',
                    stream: personal.watchOngoing(),
                    emptyMessage: 'Aucun engagement en cours.',
                  ),
          ),
          GoRoute(
            path: '/me',
            builder: (context, state) => personal == null
                ? const GuestPersonalScreen(
                    title: 'Moi',
                    message:
                        'Cette partie rassemble vos informations personnelles. Elle reste protégée tant que vous continuez sans compte.',
                  )
                : ProjectionScreen(
                    title: 'Moi',
                    stream: personal.watchMe(),
                    emptyMessage: 'Aucune information personnelle à afficher.',
                  ),
          ),
        ],
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => LoginScreen(runtime: runtime),
      ),
      GoRoute(
        path: '/create-account',
        builder: (context, state) => RegisterScreen(runtime: runtime),
      ),
      GoRoute(path: '/mark', builder: (context, state) => const MarkScreen()),
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
                message:
                    'Cette destination concerne une activité personnelle. Votre destination reste disponible après reconnexion.',
              );
            }
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
