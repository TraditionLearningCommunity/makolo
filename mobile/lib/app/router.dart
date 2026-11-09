import '../features/continuity/transverse_retrieval_screen.dart';
import '../features/continuity/space_retrieval_owner_screen.dart';
import '../features/continuity/personal_owner_depth_screen.dart';

import 'dart:async';

import 'package:flutter/material.dart';
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
import '../features/discovery/discovery_repository.dart';
import '../features/discovery/discovery_shared_link_screen.dart';
import '../features/discovery/discovery_event_tickets_screen.dart';
import '../features/discovery/discovery_ticket_order_screen.dart';
import '../features/funding/funding_contribution_screen.dart';
import '../features/commerce/commerce_checkout_screen.dart';
import '../features/commerce/commerce_order_screen.dart';
import '../features/obtention/obtention_choose_screen.dart';
import '../features/payments/payment_obligation_screen.dart';
import '../features/services/service_start_screen.dart';
import '../features/guest/public_discovery_map_screen.dart';
import '../features/guest/public_home_screen.dart';
import '../features/guest/public_possibility_detail_screen.dart';
import '../features/guest/public_space_screens.dart';
import '../features/guest/public_profile_screen.dart';
import '../features/guest/guest_screen.dart';
import '../features/interoperability/interoperability_routes.dart';
import '../features/journey/journey_routes.dart';
import '../features/mark/mark_routes.dart';
import '../features/me/me_routes.dart';
import '../features/me/passport_document_reader_screen.dart';
import '../features/me/me_group_screen.dart';
import '../features/now/now_routes.dart';
import '../features/ongoing/ongoing_routes.dart';
import '../features/preparation/preparation_routes.dart';
import '../features/questionnaires/questionnaire_routes.dart';
import '../features/settings/account_screen.dart';
import '../features/settings/billing_screen.dart';
import '../features/settings/change_password_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/space/space_shell_routes.dart';
import '../features/interoperability/space_connections_screen.dart';
import '../features/space/space_create_screen.dart';
import '../features/space/space_work_create_activity_screen.dart';
import '../features/space/space_us_settings_screen.dart';
import '../features/space/space_passport_screen.dart';
import '../features/space/space_documents_screen.dart';
import '../features/space/space_document_detail_screen.dart';
import '../features/space/space_passport_visibility_screen.dart';
import '../features/space/space_insight_screen.dart';
import '../features/space/space_work_collection_screen.dart';
import '../features/space/space_repository.dart';
import '../features/space/space_request_screen.dart';
import '../features/space/space_service_case_screen.dart';
import '../features/space/space_work_offer_editor_screen.dart';
import '../features/space/space_transport_create_screen.dart';
import '../features/space/space_transport_departure_operations_screen.dart';
import '../features/space/space_occurrence_screen.dart';
import '../features/occurrence/occurrence_scanner_screen.dart';
import '../features/occurrence/occurrence_owner_depth_screen.dart';
import '../navigation/destination.dart';
import '../navigation/secondary_screen.dart';
import '../notifications/notification_routes.dart';
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
      : '/welcome';

  DiscoveryQuery? publicDiscoveryQuery(Map<String, String> parameters) {
    // Guest routes may never silently reinterpret an explicit Profile or
    // Space request as a public field.
    if (parameters.containsKey('context') || parameters.containsKey('space'))
      return null;
    try {
      return DiscoveryQuery.fromRouteParameters(parameters);
    } on FormatException {
      return null;
    }
  }

  Widget invalidDiscoveryRoute() => const Scaffold(
    body: Center(
      child: Text(
        'Ces critères géographiques sont invalides. '
        'Revenez à Découvrir pour les modifier.',
        textAlign: TextAlign.center,
      ),
    ),
  );

  void logout() {
    unawaited(
      endMakoloAccountSession(
        runtime: runtime,
        onAuthenticationChanged: onAuthenticationChanged,
      ),
    );
  }

  bool isProtectedPath(String path) {
    if (path.startsWith('/me/')) return true;
    // These routes are public read-only projections, even when deep-linked.
    // The authenticated router still uses the canonical personal depths.
    if (path.startsWith('/commerce/activities/') ||
        path == '/welcome' ||
        path == '/discover' ||
        path == '/discover/map' ||
        path == '/spaces' ||
        path.startsWith('/spaces/') ||
        path.startsWith('/people/') ||
        path.startsWith('/events/') ||
        path.startsWith('/discover/items/') ||
        path.startsWith('/s/') ||
        path.startsWith('/passport/verify/') ||
        path.startsWith('/passport/shared/')) {
      return false;
    }
    if (MakoloDestination.forPath(path) != null) return true;
    if (const {
      '/mark',
      '/connections',
      '/conversations',
      '/history',
      '/notifications',
      '/ongoing/calendar',
      '/billing',
      '/account',
      '/account/password',
      '/settings',
      '/settings/notifications',
      '/space/create',
    }.contains(path)) {
      return true;
    }
    return const [
      '/journeys/',
      '/shares/',
      '/discover/items/',
      '/activities/',
      '/services/',
      '/tickets/orders/',
      '/commerce/journeys/',
      '/commerce/orders/',
      '/payments/obligations/',
      '/occurrences/',
      '/space/occurrences/',
      '/space/relationships',
      '/space/pilot',
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

      if (!runtime.isAuthenticated && path == '/discover/search') {
        return '/discover';
      }

      if (runtime.isAuthenticated) {
        // Legacy global links must not silently open personal entitlements or
        // connections while the user is acting for a different owner.
        if (actor is SpaceActorContext && path == '/connections') {
          return connectionsRouteForActor(actor);
        }
        if (actor is SpaceActorContext && path == '/billing') {
          return subscriptionRouteForActor(actor);
        }
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
      GoRoute(
        path: '/passport/verify/:token',
        builder: (context, state) => PassportDocumentReaderScreen(
          runtime: runtime,
          token: state.pathParameters['token']!,
          explicitShare: false,
        ),
      ),
      GoRoute(
        path: '/passport/shared/:token',
        builder: (context, state) => PassportDocumentReaderScreen(
          runtime: runtime,
          token: state.pathParameters['token']!,
          explicitShare: true,
        ),
      ),
      GoRoute(
        path: '/s/:token',
        builder: (context, state) => DiscoverySharedLinkScreen(
          runtime: runtime,
          token: state.pathParameters['token']!,
        ),
      ),
      GoRoute(
        path: '/shares/:id',
        builder: (context, state) => DiscoverySharedLinkScreen(
          runtime: runtime,
          deliveryId: state.pathParameters['id']!,
        ),
      ),
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
        ),
      if (!runtime.isAuthenticated) ...[
        GoRoute(
          path: '/welcome',
          builder: (context, state) => const PublicHomeScreen(),
        ),
        GoRoute(
          path: '/discover',
          builder: (context, state) {
            final query = publicDiscoveryQuery(state.uri.queryParameters);
            if (query == null) return invalidDiscoveryRoute();
            return GuestDiscoverScreen(
              runtime: runtime,
              initialQuery: query.text,
              initialVertical: query.vertical,
              initialFilters: state.uri.queryParameters.isEmpty ? null : query,
            );
          },
        ),
        GoRoute(
          path: '/discover/map',
          builder: (context, state) {
            final query = publicDiscoveryQuery(state.uri.queryParameters);
            if (query == null) return invalidDiscoveryRoute();
            return PublicDiscoveryMapScreen(runtime: runtime, query: query);
          },
        ),
        GoRoute(
          path: '/discover/items/:family/:id',
          builder: (context, state) {
            if (publicDiscoveryQuery(state.uri.queryParameters) == null) {
              return invalidDiscoveryRoute();
            }
            return PublicPossibilityDetailScreen(
              runtime: runtime,
              family: state.pathParameters['family']!,
              id: state.pathParameters['id']!,
            );
          },
        ),
        GoRoute(
          path: '/spaces',
          builder: (context, state) => PublicSpacesScreen(runtime: runtime),
        ),
        GoRoute(
          path: '/spaces/:slug',
          builder: (context, state) => PublicSpaceDetailScreen(
            runtime: runtime,
            slug: state.pathParameters['slug']!,
          ),
        ),
      ],
      if (runtime.isAuthenticated) ...[
        GoRoute(
          path: '/spaces',
          builder: (context, state) => PublicSpacesScreen(runtime: runtime),
        ),
        GoRoute(
          path: '/spaces/:slug',
          builder: (context, state) => PublicSpaceDetailScreen(
            runtime: runtime,
            slug: state.pathParameters['slug']!,
          ),
        ),
        GoRoute(
          path: '/services/:id/start',
          builder: (context, state) => ServiceStartScreen(
            runtime: runtime,
            serviceId: state.pathParameters['id']!,
          ),
        ),
      ],
      GoRoute(
        path: '/obtention/:id/choose',
        builder: (context, state) => ObtentionChooseScreen(
          runtime: runtime,
          obtentionId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/funding/:id/contribute',
        builder: (context, state) => FundingContributionScreen(
          runtime: runtime,
          fundingId: state.pathParameters['id']!,
        ),
      ),
      if (runtime.isAuthenticated)
        GoRoute(
          path: '/payments/obligations/:id',
          builder: (context, state) => PaymentObligationScreen(
            runtime: runtime,
            obligationId: state.pathParameters['id']!,
          ),
        ),
      GoRoute(
        path: '/commerce/activities/:id/checkout',
        builder: (context, state) => CommerceCheckoutScreen(
          runtime: runtime,
          activityId: state.pathParameters['id']!,
        ),
      ),
      if (runtime.isAuthenticated) ...[
        GoRoute(
          path: '/commerce/journeys/:id/checkout',
          builder: (context, state) => CommerceCheckoutScreen(
            runtime: runtime,
            journeyId: state.pathParameters['id']!,
          ),
        ),
        GoRoute(
          path: '/commerce/orders/:id',
          builder: (context, state) => CommerceOrderScreen(
            runtime: runtime,
            orderId: state.pathParameters['id']!,
          ),
        ),
      ],
      GoRoute(
        path: '/events/:slug/tickets',
        builder: (context, state) => DiscoveryEventTicketsScreen(
          runtime: runtime,
          eventSlug: state.pathParameters['slug']!,
        ),
      ),
      if (runtime.isAuthenticated)
        GoRoute(
          path: '/tickets/orders/:id',
          builder: (context, state) => DiscoveryTicketOrderScreen(
            runtime: runtime,
            orderId: state.pathParameters['id']!,
          ),
        ),
      GoRoute(
        path: '/people/:id',
        builder: (context, state) => PublicProfileScreen(
          runtime: runtime,
          profileId: state.pathParameters['id']!,
        ),
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
          onClose: () {
            if (context.canPop()) {
              context.pop();
            } else {
              final actor =
                  runtime.actorContext?.value ?? const PersonalActorContext();
              context.go(
                runtime.isAuthenticated
                    ? MakoloDestination.forActor(
                        actor,
                        MakoloPrimaryDoor.now,
                      ).path
                    : '/welcome',
              );
            }
          },
        ),
      ),
      GoRoute(
        path: '/billing',
        builder: (context, state) => BillingScreen(runtime: runtime),
      ),
      GoRoute(
        path: '/account',
        builder: (context, state) => AccountScreen(
          runtime: runtime,
          onChangePassword: () => context.push('/account/password'),
          onRememberedAccounts: () => context.push('/accounts'),
        ),
      ),
      GoRoute(
        path: '/account/password',
        builder: (context, state) => ChangePasswordScreen(
          runtime: runtime,
          onPasswordChanged: onAuthenticationChanged,
        ),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) => AppSettingsScreen(
          runtime: runtime,
          onNotifications: () => context.push('/settings/notifications'),
          onSecurity: () => context.push('/account'),
          onPrivacy: () => context.push('/me/profile?visibility=1'),
        ),
      ),
      GoRoute(
        path: '/space/create',
        builder: (context, state) => SpaceCreateScreen(runtime: runtime),
      ),
      ...interoperabilityRoutes(runtime),
      GoRoute(
        path: '/space/:slug/connections',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Connexions du Space',
              message: 'Choisissez un Espace autorisé.',
            );
          }
          return SpaceConnectionsScreen(
            runtime: runtime,
            slug: actor.space.slug,
          );
        },
      ),
      ...markRoutes(runtime, onLogout: logout),
      ...continuityRoutes(runtime),
      ...notificationRoutes(runtime),
      GoRoute(
        path: '/space/requests/:id',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Demande de cet Espace',
              message: 'Choisissez un Espace autorisé.',
            );
          }
          return SpaceRequestScreen(
            runtime: runtime,
            actor: actor,
            requestId: state.pathParameters['id']!,
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/work/g3/departures/:id/operate',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Exploiter le départ',
              message: 'Choisissez le contexte autorisé de cet Espace.',
            );
          }
          return SpaceTransportDepartureOperationsScreen(
            runtime: runtime,
            actor: actor,
            departureId: state.pathParameters['id']!,
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/work/g3/transport/new',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug'] ||
              !actor.perspective.isAll) {
            return const MakoloSecondaryScreen(
              title: 'Créer dans Transport',
              message: 'Choisissez cet Espace et sa responsabilité globale.',
            );
          }
          return SpaceTransportCreateScreen(runtime: runtime, actor: actor);
        },
      ),
      GoRoute(
        path: '/space/:slug/work/g3/activities/:activityId/offers/new',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Nouvelle offre',
              message: 'Choisissez le contexte autorisé de cet Espace.',
            );
          }
          return SpaceWorkOfferEditorScreen(
            runtime: runtime,
            actor: actor,
            activityId: state.pathParameters['activityId']!,
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/work/g3/offers/:offerId/edit',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Modifier l’offre',
              message: 'Choisissez le contexte autorisé de cet Espace.',
            );
          }
          return SpaceWorkOfferEditorScreen(
            runtime: runtime,
            actor: actor,
            offerId: state.pathParameters['offerId']!,
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/work/g2/new',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug'] ||
              !actor.perspective.isAll) {
            return const MakoloSecondaryScreen(
              title: 'Créer dans Métier',
              message: 'Choisissez votre Espace et sa responsabilité globale.',
            );
          }
          return SpaceWorkCreateActivityScreen(
            runtime: runtime,
            actor: actor,
            isCommunity: false,
            archetype: state.uri.queryParameters['archetype'],
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/work/activities/new',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug'] ||
              !actor.perspective.isAll) {
            return const MakoloSecondaryScreen(
              title: 'Nouvelle activité',
              message: 'Choisissez votre Espace et sa responsabilité globale.',
            );
          }
          return SpaceWorkCreateActivityScreen(
            runtime: runtime,
            actor: actor,
            isCommunity: state.uri.queryParameters['archetype'] == 'community',
            archetype: state.uri.queryParameters['archetype'],
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/work/:section',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Métier',
              message: 'Choisissez l’Espace autorisé pour cette collection.',
            );
          }
          return SpaceWorkCollectionScreen(
            runtime: runtime,
            actor: actor,
            section: state.pathParameters['section']!,
          );
        },
      ),
      GoRoute(
        path: '/me/orders/:id',
        builder: (context, state) => PersonalOwnerDepthScreen(
          runtime: runtime,
          kind: 'commerce_order',
          id: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/space/:slug/services/cases/:id',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Dossier de prestation',
              message: 'Choisissez le contexte autorisé de cet Espace.',
            );
          }
          return SpaceServiceCaseScreen(
            runtime: runtime,
            actor: actor,
            journeyId: state.pathParameters['id']!,
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/retrieval/:kind/:id',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Détail de mon Espace',
              message: 'Choisissez l’Espace autorisé pour ce détail.',
            );
          }
          return SpaceRetrievalOwnerScreen(
            runtime: runtime,
            spaceActor: actor,
            kind: state.pathParameters['kind']!,
            id: state.pathParameters['id']!,
            workSection: state.uri.queryParameters['work_section'],
            fromWorkCollection:
                state.uri.queryParameters['work_collection'] == '1',
          );
        },
      ),
      GoRoute(
        path: '/search',
        builder: (context, state) => TransverseRetrievalScreen(
          runtime: runtime,
          initialQuery: state.uri.queryParameters['q'] ?? '',
        ),
      ),
      GoRoute(
        path: '/space/search',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Recherche',
              message: 'Choisissez un Espace autorisé.',
            );
          }
          return TransverseRetrievalScreen(
            runtime: runtime,
            spaceActor: actor,
            initialQuery: state.uri.queryParameters['q'] ?? '',
          );
        },
      ),
      GoRoute(
        path: '/space/history',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Historique',
              message: 'Choisissez un Espace autorisé.',
            );
          }
          return TransverseRetrievalScreen(
            runtime: runtime,
            spaceActor: actor,
            history: true,
            initialQuery: state.uri.queryParameters['q'] ?? '',
          );
        },
      ),
      ...discoveryRoutes(runtime),
      ...ongoingRoutes(runtime),
      ...journeyRoutes(runtime),
      ...preparationRoutes(runtime),
      ...questionnaireRoutes(runtime),
      ...dayOfRoutes(runtime),
      ...liveRoutes(runtime),
      GoRoute(
        path: '/occurrences/:id/depth/:kind',
        builder: (context, state) {
          if (runtime.api == null ||
              runtime.actorContext?.value is SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Profondeur métier',
              message: 'Ouvrez cette profondeur depuis le bon acteur.',
            );
          }
          return OccurrenceOwnerDepthScreen(
            runtime: runtime,
            occurrenceId: state.pathParameters['id']!,
            kind: state.pathParameters['kind']!,
          );
        },
      ),
      GoRoute(
        path: '/space/occurrences/:id/depth/:kind',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (runtime.api == null || actor is! SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Profondeur métier',
              message: 'Le contexte Space autorisé est requis.',
            );
          }
          return OccurrenceOwnerDepthScreen(
            runtime: runtime,
            occurrenceId: state.pathParameters['id']!,
            kind: state.pathParameters['kind']!,
            actorSpaceId: actor.space.id,
          );
        },
      ),
      GoRoute(
        path: '/occurrences/:id/scanner',
        builder: (context, state) {
          if (runtime.api == null ||
              runtime.actorContext?.value is SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Scanner',
              message: 'Ouvrez le Scanner depuis le contexte autorisé.',
            );
          }
          return OccurrenceScannerScreen(
            runtime: runtime,
            occurrenceId: state.pathParameters['id']!,
          );
        },
      ),
      GoRoute(
        path: '/space/occurrences/:id/scanner',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (runtime.api == null || actor is! SpaceActorContext) {
            return const MakoloSecondaryScreen(
              title: 'Scanner',
              message: 'Un Espace mandaté est requis pour le contrôle.',
            );
          }
          return OccurrenceScannerScreen(
            runtime: runtime,
            occurrenceId: state.pathParameters['id']!,
            actorSpaceId: actor.space.id,
          );
        },
      ),
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
            actorContext: runtime.actorContext,
            live: false,
            onOpenLive: () => context.push(
              '/space/occurrences/${state.pathParameters['id']}/live',
            ),
            onOpenScanner: () => context.push(
              '/space/occurrences/${state.pathParameters['id']}/scanner',
            ),
            onOpenDepth: (kind) => context.push(
              '/space/occurrences/${state.pathParameters['id']}/depth/${Uri.encodeComponent(kind)}',
            ),
            onOpenHistory: () => context.push('/space/history'),
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
            actorContext: runtime.actorContext,
            live: true,
            onBackToDayOf: () => context.go(
              '/space/occurrences/${state.pathParameters['id']}/day-of',
            ),
            onOpenDepth: (kind) => context.push(
              '/space/occurrences/${state.pathParameters['id']}/depth/${Uri.encodeComponent(kind)}',
            ),
          );
        },
      ),
      ...accessRoutes(runtime),
      GoRoute(
        path: '/space/:slug/us/relationships',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Personnes & relations',
              message: 'Sélectionnez le Space autorisé pour cette relation.',
            );
          }
          return SpaceInsightScreen(
            runtime: runtime,
            surface: SpaceProjectionKind.relationships,
            expectedSlug: state.pathParameters['slug'],
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/us/pilot',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          if (actor is! SpaceActorContext ||
              actor.space.slug != state.pathParameters['slug']) {
            return const MakoloSecondaryScreen(
              title: 'Piloter',
              message: 'Sélectionnez le Space autorisé pour cette analyse.',
            );
          }
          return SpaceInsightScreen(
            runtime: runtime,
            surface: SpaceProjectionKind.pilot,
            expectedSlug: state.pathParameters['slug'],
          );
        },
      ),
      GoRoute(
        path: '/space/relationships',
        builder: (context, state) => SpaceInsightScreen(
          runtime: runtime,
          surface: SpaceProjectionKind.relationships,
        ),
      ),
      GoRoute(
        path: '/space/pilot',
        builder: (context, state) => SpaceInsightScreen(
          runtime: runtime,
          surface: SpaceProjectionKind.pilot,
        ),
      ),
      GoRoute(
        path: '/space/:slug/subscription',
        builder: (context, state) {
          final actor = runtime.actorContext?.value;
          final slug = state.pathParameters['slug']!;
          if (actor is! SpaceActorContext || actor.space.slug != slug) {
            return const MakoloSecondaryScreen(
              title: 'Abonnement de l’Espace',
              message: 'Choisissez cet Espace dans « Agir comme » pour consulter son abonnement.',
            );
          }
          return BillingScreen(
            runtime: runtime,
            spaceSlug: slug,
            expectedSpaceId: actor.space.id,
            fromTeam: state.uri.queryParameters['from'] == 'team',
          );
        },
      ),
      GoRoute(
        path: '/space/:slug/us/passport/privacy',
        builder: (context, state) => SpacePassportVisibilityScreen(
          runtime: runtime,
          slug: state.pathParameters['slug']!,
        ),
      ),
      GoRoute(
        path: '/space/:slug/us/passport',
        builder: (context, state) => SpacePassportScreen(
          runtime: runtime,
          slug: state.pathParameters['slug']!,
        ),
      ),
      GoRoute(
        path: '/space/:slug/us/documents',
        builder: (context, state) => SpaceDocumentsScreen(
          runtime: runtime,
          slug: state.pathParameters['slug']!,
        ),
      ),
      GoRoute(
        path: '/space/:slug/us/documents/:id',
        builder: (context, state) => SpaceDocumentDetailScreen(
          runtime: runtime,
          slug: state.pathParameters['slug']!,
          documentId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/space/:slug/us/settings',
        builder: (context, state) => SpaceUsSettingsScreen(
          runtime: runtime,
          slug: state.pathParameters['slug']!,
        ),
      ),
      GoRoute(
        path: '/space/:slug/us/:depth',
        builder: (context, state) => SpaceNousDepthScreen(
          runtime: runtime,
          slug: state.pathParameters['slug']!,
          depth: state.pathParameters['depth']!,
        ),
      ),
      GoRoute(
        path: '/groups/:id',
        builder: (context, state) {
          runtime.recovery.rememberLocation(state.uri.toString());
          if (runtime.api == null) {
            return const MakoloSecondaryScreen(
              title: 'Groupe',
              message: 'Ce groupe est momentanément indisponible.',
            );
          }
          return MeGroupScreen(
            api: runtime.api!,
            groupId: state.pathParameters['id']!,
            conversations: runtime.conversations,
            onOpenConversation: (id) => context.push('/conversations/$id'),
          );
        },
      ),
    ],
  );
}
