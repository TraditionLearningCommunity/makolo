import 'dart:async';

import 'package:go_router/go_router.dart';

import '../features/auth/account_actions.dart';
import '../features/auth/account_chooser_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/signup_screen.dart';
import '../features/discovery/discovery_screens.dart';
import '../features/guest/guest_screen.dart';
import '../features/interoperability/connections_screen.dart';
import '../features/journey/journey_detail_screen.dart';
import '../features/journey/journey_selector.dart';
import '../features/mark/mark_screen.dart';
import '../features/personal/placeholder_screen.dart';
import '../features/personal/projection_screen.dart';
import '../features/questionnaires/questionnaire_form_screen.dart';
import '../features/questionnaires/questionnaire_repository.dart';
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

  void logout() {
    unawaited(
      endMakoloAccountSession(
        runtime: runtime,
        onAuthenticationChanged: onAuthenticationChanged,
      ),
    );
  }

  bool isProtectedPath(String path) {
    if (const {
      '/now',
      '/ongoing',
      '/me',
      '/mark',
      '/connections',
      '/conversations',
      '/notifications',
      '/ongoing/calendar',
    }.contains(path)) {
      return true;
    }
    return const [
      '/journeys/',
      '/discover/items/',
      '/activities/',
      '/occurrences/',
      '/accesses/',
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

      if (runtime.isAuthenticated &&
          (path == '/login' || path == '/create-account') &&
          !switchingAccount &&
          !addingAccount) {
        return '/now';
      }

      if (!runtime.isAuthenticated && isProtectedPath(path)) {
        runtime.recovery.requireAuthentication(state.uri.toString());
        return '/login';
      }

      if (!runtime.isAuthenticated &&
          (path == '/discover/search' || path == '/discover/filters')) {
        return '/discover';
      }

      return null;
    },
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
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/now',
                  builder: (context, state) => MakoloRefreshBoundary(
                    child: ProjectionScreen(
                      title: 'Now',
                      stream: personal!.watchNow(),
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
                  builder: (context, state) {
                    final discovery = runtime.discovery;
                    if (discovery == null) {
                      return const MakoloRefreshBoundary(
                        child: PlaceholderScreen(
                          title: 'Découvrir',
                          message:
                              'Découvrir n’est pas disponible sur cet appareil.',
                          showTitle: false,
                        ),
                      );
                    }
                    return MakoloRefreshBoundary(
                      child: DiscoveryScreen(
                        repository: discovery,
                        location: runtime.location,
                        onOpenActivity: (id) =>
                            context.push('/activities/$id'),
                        onOpenOccurrence: (id) =>
                            context.push('/occurrences/$id'),
                        onOpenItem: (family, id) => context.push(
                          '/discover/items/$family/$id',
                        ),
                      ),
                    );
                  },
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
                      stream: personal!.watchOngoing(),
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
                      stream: personal!.watchMe(),
                      emptyMessage:
                          'Aucune information à afficher pour le moment.',
                      showTitle: false,
                    ),
                  ),
                ),
              ],
            ),
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
        path: '/connections',
        builder: (context, state) => MakoloRefreshBoundary(
          child: ProfileConnectionsScreen(runtime: runtime),
        ),
      ),
      GoRoute(
        path: '/mark',
        builder: (context, state) => MarkScreen(runtime: runtime),
      ),
      GoRoute(
        path: '/conversations',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Conversations',
          message: 'Aucune conversation à afficher pour le moment.',
        ),
      ),
      GoRoute(
        path: '/notifications',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Notifications',
          message: 'Rien de nouveau pour le moment.',
        ),
      ),
      GoRoute(
        path: '/discover/search',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Rechercher',
          message: 'Recherchez une possibilité.',
        ),
      ),
      GoRoute(
        path: '/discover/filters',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Filtres',
          message: 'Aucun filtre actif.',
        ),
      ),
      GoRoute(
        path: '/discover/items/:family/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final discovery = runtime.discovery;
          if (discovery == null) {
            return const MakoloSecondaryScreen(
              title: 'Possibilité',
              message: 'Ce détail n’est pas disponible sur cet appareil.',
            );
          }
          return DiscoveryItemDetailScreen(
            family: state.pathParameters['family']!,
            id: state.pathParameters['id']!,
            repository: discovery,
          );
        },
      ),
      GoRoute(
        path: '/activities/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final discovery = runtime.discovery;
          if (discovery == null) {
            return const MakoloSecondaryScreen(
              title: 'Activité',
              message: 'Cette activité n’est pas disponible sur cet appareil.',
            );
          }
          return ActivityDetailScreen(
            activityId: state.pathParameters['id']!,
            repository: discovery,
            onOpenOccurrence: (id) => context.push('/occurrences/$id'),
          );
        },
      ),
      GoRoute(
        path: '/occurrences/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final discovery = runtime.discovery;
          if (discovery == null) {
            return const MakoloSecondaryScreen(
              title: 'Occurrence',
              message:
                  'Cette occurrence n’est pas disponible sur cet appareil.',
            );
          }
          return OccurrenceDetailScreen(
            occurrenceId: state.pathParameters['id']!,
            repository: discovery,
            onOpenActivity: (id) => context.push('/activities/$id'),
          );
        },
      ),
      GoRoute(
        path: '/ongoing/calendar',
        builder: (context, state) => const MakoloSecondaryScreen(
          title: 'Calendrier',
          message: 'Aucune date à afficher pour le moment.',
        ),
      ),
      GoRoute(
        path: '/journeys/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final journeys = runtime.journeys;
          if (journeys == null) {
            return const MakoloSecondaryScreen(
              title: 'Démarche',
              message: 'Cette démarche n’est pas disponible sur cet appareil.',
            );
          }
          return JourneyDetailScreen(
            journeyId: state.pathParameters['id']!,
            repository: journeys,
            onOpenForm: (form) {
              context.push(
                '/journeys/${state.pathParameters['id']!}/forms/${form.id}',
                extra: form,
              );
            },
          );
        },
      ),
      GoRoute(
        path: '/journeys/:journeyId/forms/:requestId',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final form = state.extra is JourneyFormSummary
              ? state.extra! as JourneyFormSummary
              : null;
          final questionnaires = runtime.questionnaires;
          final drafts = runtime.drafts;
          final outbox = runtime.outbox;
          final submit = runtime.questionnaireSubmit;
          if (form == null ||
              questionnaires == null ||
              drafts == null ||
              outbox == null ||
              submit == null ||
              form.detailLink.isEmpty) {
            return const MakoloSecondaryScreen(
              title: 'Formulaire',
              message: 'Rouvrez ce formulaire depuis la démarche pour reprendre avec les liens du propriétaire.',
            );
          }
          return QuestionnaireFormScreen(
            requestId: state.pathParameters['requestId']!,
            journeyId: state.pathParameters['journeyId']!,
            links: QuestionnaireOwnerLinks(
              detail: form.detailLink,
              save: form.saveLink,
              submit: form.submitLink,
            ),
            repository: questionnaires,
            drafts: drafts,
            outbox: outbox,
            submitCoordinator: submit,
            outboxProcessor: runtime.outboxProcessor,
          );
        },
      ),
      for (final prefix in const [
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
              title: 'Makolo',
              message: 'Aucun détail supplémentaire à afficher pour le moment.',
            );
          },
        ),
    ],
  );
}
