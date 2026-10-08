import 'dart:async';

import 'package:go_router/go_router.dart';

import '../features/access/access_routes.dart';
import '../features/auth/account_actions.dart';
import '../features/auth/account_chooser_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/signup_screen.dart';
import '../features/continuity/continuity_routes.dart';
import '../features/day_of/day_of_routes.dart';
import '../features/live/live_routes.dart';
import '../features/discovery/discovery_routes.dart';
import '../features/guest/guest_screen.dart';
import '../features/interoperability/interoperability_routes.dart';
import '../features/journey/journey_routes.dart';
import '../features/mark/mark_routes.dart';
import '../features/me/me_routes.dart';
import '../features/now/now_routes.dart';
import '../features/ongoing/ongoing_routes.dart';
import '../features/preparation/preparation_routes.dart';
import '../features/questionnaires/questionnaire_routes.dart';
import '../features/settings/billing_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/space/space_shell_routes.dart';
import '../features/space/space_occurrence_screen.dart';
import '../navigation/destination.dart';
import '../navigation/secondary_screen.dart';
import 'app_shell.dart';
import 'runtime/actor_context.dart';
import 'runtime/app_runtime.dart';

GoRouter createMakoloRouter(
  AppRuntime runtime, {
  required void Function() onAuthenticationChanged,
}) {
  final initialLocation = runtime.isAuthenticated
      ? runtime.recovery.initialLocation()
      : runtime.recovery.awaitingAuthentication
      ? '/login'
      : '/discover';

  void logout() {
    unawaited(
      endMakoloAccountSession(
        runtime: runtime,
        onAuthenticationChanged: onAuthenticationChanged,
      ),
    );
  }

  bool isProtectedPath(String path) {
    if (path == '/discover') return false;
    if (MakoloDestination.forPath(path) != null) return true;
    if (const {
      '/mark',
      '/connections',
      '/conversations',
      '/history',
      '/notifications',
      '/ongoing/calendar',
      '/billing',
      '/settings',
    }.contains(path)) {
      return true;
    }
    return const [
      '/journeys/',
      '/discover/items/',
      '/activities/',
      '/occurrences/',
      '/space/occurrences/',
      '/accesses/',
      '/conversations/',
      '/dossiers/',
      '/projects/',
      '/groups/',
    ].any(path.startsWith);
  }

  return GoRouter(
    initialLocation: initialLocation,
    redirect: (context, state) {
      final path = state.uri.path;
      final switchingAccount = state.uri.queryParameters['switch'] == '1';
      final addingAccount = state.uri.queryParameters['add'] == '1';
      final actor = runtime.actorContext?.value ?? const PersonalActorContext();

      if (runtime.isAuthenticated &&
          (path == '/login' || path == '/create-account') &&
          !switchingAccount &&
          !addingAccount) {
        return MakoloDestination.forActor(actor, MakoloPrimaryDoor.now).path;
      }

      if (!runtime.isAuthenticated && isProtectedPath(path)) {
        runtime.recovery.requireAuthentication(state.uri.toString());
        return '/login';
      }

      if (!runtime.isAuthenticated &&
          (path == '/discover/search' || path == '/discover/map')) {
        return '/discover';
      }

      if (runtime.isAuthenticated) {
        final shellDestination = MakoloDestination.forPath(path);
        if (shellDestination != null) {
          final actorDestination = MakoloDestination.forActor(
            actor,
            shellDestination.door,
          );
          if (actorDestination.path != path) return actorDestination.path;
        }
      }

      return null;
    },
    errorBuilder: (context, state) => const MakoloSecondaryScreen(
      title: 'Makolo',
      message: 'Cette page n’est pas disponible.',
    ),
    routes: [
      if (runtime.isAuthenticated)
        StatefulShellRoute.indexedStack(
          builder: (context, state, navigationShell) => AppShell(
            navigationShell: navigationShell,
            recovery: runtime.recovery,
            runtime: runtime,
            onSwitchAccount: () {
              runtime.recovery.markAccountSwitch();
              context.push('/accounts');
            },
            onLogout: logout,
          ),
          branches: [
            nowBranch(runtime),
            discoveryBranch(runtime),
            ongoingBranch(runtime),
            meBranch(runtime),
            spaceNowBranch(runtime),
            spaceDiscoveryBranch(runtime),
            spaceWorkBranch(runtime),
            spaceUsBranch(runtime),
          ],
        )
      else
        GoRoute(
          path: '/discover',
          builder: (context, state) => GuestDiscoverScreen(runtime: runtime),
        ),
      GoRoute(
        path: '/login',
        builder: (context, state) => LoginScreen(
          runtime: runtime,
          initialEmail: state.uri.queryParameters['email'],
          startWithAccounts: state.uri.queryParameters['accounts'] == '1',
        ),
      ),
      GoRoute(
        path: '/create-account',
        builder: (context, state) => SignupScreen(
          runtime: runtime,
          onBackToLogin: (email) => context.go(
            email.isEmpty
                ? '/login'
                : '/login?email=${Uri.encodeQueryComponent(email)}',
          ),
          onAuthenticated: onAuthenticationChanged,
        ),
      ),
      GoRoute(
        path: '/accounts',
        builder: (context, state) => DeviceAccountsScreen(
          runtime: runtime,
          onUsePassword: (email) => context.push(
            '/login?switch=1&email=${Uri.encodeQueryComponent(email)}',
          ),
          onAddAccount: () => context.push('/login?add=1'),
        ),
      ),
      GoRoute(
        path: '/billing',
        builder: (context, state) => const BillingScreen(),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) => AppSettingsScreen(runtime: runtime),
      ),
      ...interoperabilityRoutes(runtime),
      ...markRoutes(runtime),
      ...continuityRoutes(runtime),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Notifications',
          message: 'Rien de nouveau pour le moment.',
        ),
      ),
      ...discoveryRoutes(runtime),
      ...ongoingRoutes(runtime),
      ...journeyRoutes(runtime),
      ...preparationRoutes(runtime),
      ...questionnaireRoutes(runtime),
      ...dayOfRoutes(runtime),
      ...liveRoutes(runtime),
      GoRoute(
        path: '/space/occurrences/:id/day-of',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          final repository = runtime.spaceOccurrences;
          if (actor is! SpaceActorContext || repository == null) {
            return const MakoloSecondaryScreen(
              title: 'Jour J Space',
              message: 'Cette Occurrence n’est pas disponible dans le contexte Space actuel.',
            );
          }
          return SpaceOccurrenceScreen(
            space: actor.space,
            occurrenceId: state.pathParameters['id']!,
            repository: repository,
            live: false,
            onOpenLive: () => context.push(
              '/space/occurrences/${state.pathParameters['id']}/live',
            ),
          );
        },
      ),
      GoRoute(
        path: '/space/occurrences/:id/live',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          final repository = runtime.spaceOccurrences;
          if (actor is! SpaceActorContext || repository == null) {
            return const MakoloSecondaryScreen(
              title: 'Live Space',
              message:
                  'Le Live opérateur n’est pas disponible dans ce contexte.',
            );
          }
          return SpaceOccurrenceScreen(
            space: actor.space,
            occurrenceId: state.pathParameters['id']!,
            repository: repository,
            live: true,
            onBackToDayOf: () => context.go(
              '/space/occurrences/${state.pathParameters['id']}/day-of',
            ),
          );
        },
      ),
      ...accessRoutes(runtime),
      GoRoute(
        path: '/groups/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          return const MakoloSecondaryScreen(
            title: 'Makolo',
            message: 'Aucun détail supplémentaire à afficher pour le moment.',
          );
        },
      ),
    ],
  );
}
