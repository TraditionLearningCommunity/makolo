import 'dart:async';

import 'package:go_router/go_router.dart';

import '../features/auth/account_actions.dart';
import '../features/auth/account_chooser_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/signup_screen.dart';
import '../features/access/access_credential_screen.dart';
import '../features/access/access_detail_screen.dart';
import '../features/continuity/conversation_screens.dart';
import '../features/continuity/history_screen.dart';
import '../features/continuity/objective_repository.dart';
import '../features/continuity/objective_screen.dart';
import '../features/discovery/discovery_screens.dart';
import '../features/discovery/discovery_watch_screens.dart';
import '../features/day_of/day_of_screen.dart';
import '../features/guest/guest_screen.dart';
import '../features/interoperability/connections_screen.dart';
import '../features/journey/journey_detail_screen.dart';
import '../features/journey/journey_selector.dart';
import '../features/mark/mark_screen.dart';
import '../features/preparation/preparation_resources_screen.dart';
import '../features/preparation/requirement_detail_screen.dart';
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
      '/history',
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
                          message: 'Découvrir n’est pas disponible sur cet appareil.',
                          showTitle: false,
                        ),
                      );
                    }
                    return MakoloRefreshBoundary(
                      child: DiscoveryScreen(
                        repository: discovery,
                        location: runtime.location,
                        onOpenActivity: (id) => context.push('/activities/$id'),
                        onOpenOccurrence: (id) =>
                            context.push('/occurrences/$id'),
                        onOpenItem: (family, id) =>
                            context.push('/discover/items/$family/$id'),
                        onOpenWatches: () => context.push('/discover/watches'),
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
        builder: (context, state) {
          final conversations = runtime.conversations;
          if (conversations == null) {
            return const MakoloSecondaryScreen(
              title: 'Conversations',
              message: 'Aucune conversation à afficher pour le moment.',
            );
          }
          return ConversationListScreen(
            repository: conversations,
            onOpen: (id) => context.push('/conversations/$id'),
          );
        },
      ),
      GoRoute(
        path: '/conversations/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final conversations = runtime.conversations;
          if (conversations == null) {
            return const MakoloSecondaryScreen(
              title: 'Conversation',
              message:
                  'Cette conversation n’est pas disponible sur cet appareil.',
            );
          }
          return ConversationDetailScreen(
            id: state.pathParameters['id']!,
            repository: conversations,
          );
        },
      ),
      GoRoute(
        path: '/history',
        builder: (context, state) {
          final history = runtime.history;
          if (history == null) {
            return const MakoloSecondaryScreen(
              title: 'Historique',
              message: 'Aucun historique à afficher pour le moment.',
            );
          }
          return HistoryScreen(
            repository: history,
            onOpenResource: (kind, id) {
              if (kind == 'journey') {
                context.push('/journeys/$id');
              } else if (kind == 'access') {
                context.push('/accesses/$id');
              }
            },
          );
        },
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
        path: '/discover/watches',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final discovery = runtime.discovery;
          if (discovery == null) {
            return const MakoloSecondaryScreen(
              title: 'Veilles',
              message: 'Les veilles ne sont pas disponibles sur cet appareil.',
            );
          }
          return DiscoveryWatchesScreen(
            repository: discovery,
            onOpenWatch: (id) => context.push('/discover/watches/$id'),
          );
        },
      ),
      GoRoute(
        path: '/discover/watches/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final discovery = runtime.discovery;
          if (discovery == null) {
            return const MakoloSecondaryScreen(
              title: 'Veille',
              message: 'Cette veille n’est pas disponible sur cet appareil.',
            );
          }
          return DiscoveryWatchResultsScreen(
            watchId: state.pathParameters['id']!,
            repository: discovery,
            onOpenActivity: (id) => context.push('/activities/$id'),
            onOpenItem: (family, id) =>
                context.push('/discover/items/$family/$id'),
          );
        },
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
            onOpenDayOf: () => context.push(
              '/occurrences/${state.pathParameters['id']!}/day-of',
            ),
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
            onOpenRequirement: (requirement) {
              context.push(
                '/journeys/${state.pathParameters['id']!}/requirements/${requirement.id}',
                extra: requirement,
              );
            },
            onOpenResources: (resourcesLink) {
              context.push(
                '/journeys/${state.pathParameters['id']!}/resources',
                extra: resourcesLink,
              );
            },
          );
        },
      ),
      GoRoute(
        path: '/journeys/:journeyId/requirements/:assessmentId',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final requirements = runtime.requirements;
          if (requirements == null) {
            return const MakoloSecondaryScreen(
              title: 'Élément nécessaire',
              message: 'Ce détail n’est pas disponible sur cet appareil.',
            );
          }
          final reference = state.extra is JourneyReference
              ? state.extra! as JourneyReference
              : null;
          return RequirementDetailScreen(
            journeyId: state.pathParameters['journeyId']!,
            assessmentId: state.pathParameters['assessmentId']!,
            detailPath: reference?.link,
            repository: requirements,
          );
        },
      ),
      GoRoute(
        path: '/journeys/:journeyId/resources',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final resources = runtime.preparationResources;
          if (resources == null) {
            return const MakoloSecondaryScreen(
              title: 'Documents et instructions',
              message:
                  'Ces ressources ne sont pas disponibles sur cet appareil.',
            );
          }
          return PreparationResourcesScreen(
            journeyId: state.pathParameters['journeyId']!,
            resourcesPath: state.extra is String
                ? state.extra! as String
                : null,
            repository: resources,
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
      GoRoute(
        path: '/occurrences/:id/day-of',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final dayOf = runtime.dayOf;
          if (dayOf == null) {
            return const MakoloSecondaryScreen(
              title: 'Jour J',
              message: 'Le Jour J n’est pas disponible sur cet appareil.',
            );
          }
          return DayOfScreen(
            occurrenceId: state.pathParameters['id']!,
            repository: dayOf,
            onOpenAccess: (accessId, detailPath) =>
                context.push('/accesses/$accessId'),
            onPresentCredential: (accessId, credentialPath) => context.push(
              '/accesses/$accessId/credential',
              extra: credentialPath,
            ),
          );
        },
      ),
      GoRoute(
        path: '/accesses/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final accesses = runtime.accesses;
          if (accesses == null) {
            return const MakoloSecondaryScreen(
              title: 'Accès',
              message: 'Cet accès n’est pas disponible sur cet appareil.',
            );
          }
          return AccessDetailScreen(
            accessId: state.pathParameters['id']!,
            repository: accesses,
            onOpenDayOf: (handoff) =>
                context.push('/occurrences/${handoff.occurrenceId}/day-of'),
            onOpenJourney: (journeyId) => context.push('/journeys/$journeyId'),
          );
        },
      ),
      GoRoute(
        path: '/accesses/:id/credential',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final accesses = runtime.accesses;
          final credentialPath = state.extra is String
              ? state.extra! as String
              : null;
          if (accesses == null || credentialPath == null) {
            return const MakoloSecondaryScreen(
              title: 'QR d’accès',
              message: 'Rouvrez ce QR depuis le Jour J afin de revalider son lien propriétaire.',
            );
          }
          return AccessCredentialScreen(
            accessId: state.pathParameters['id']!,
            credentialPath: credentialPath,
            repository: accesses,
          );
        },
      ),
      GoRoute(
        path: '/dossiers/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final objectives = runtime.objectives;
          if (objectives == null) {
            return const MakoloSecondaryScreen(
              title: 'Dossier',
              message: 'Ce dossier n’est pas disponible sur cet appareil.',
            );
          }
          return ObjectiveDetailScreen(
            kind: ObjectiveDepth.dossier,
            id: state.pathParameters['id']!,
            repository: objectives,
            onOpenDossier: (id) => context.push('/dossiers/$id'),
            onOpenJourney: (id) => context.push('/journeys/$id'),
          );
        },
      ),
      GoRoute(
        path: '/projects/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          final objectives = runtime.objectives;
          if (objectives == null) {
            return const MakoloSecondaryScreen(
              title: 'Projet',
              message: 'Ce projet n’est pas disponible sur cet appareil.',
            );
          }
          return ObjectiveDetailScreen(
            kind: ObjectiveDepth.project,
            id: state.pathParameters['id']!,
            repository: objectives,
            onOpenDossier: (id) => context.push('/dossiers/$id'),
            onOpenJourney: (id) => context.push('/journeys/$id'),
          );
        },
      ),
      for (final prefix in const ['groups'])
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
