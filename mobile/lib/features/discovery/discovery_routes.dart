import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../app/runtime/actor_context.dart';
import '../../navigation/refresh_boundary.dart';
import '../../navigation/secondary_screen.dart';
import '../personal/placeholder_screen.dart';
import 'discovery_screens.dart';
import 'discovery_repository.dart';
import 'discovery_watch_screens.dart';

DiscoveryQuery? _routeQuery(Map<String, String> params, AppRuntime runtime) {
  try {
    final query = DiscoveryQuery.fromRouteParameters(params);
    final actor = runtime.actorContext?.value;
    // A bare Discovery link never escapes the active Space to reveal
    // personal Saves, engagements or a differently scoped detail.
    if (!query.isSpace) {
      return actor is SpaceActorContext ? null : query;
    }
    if (actor is! SpaceActorContext || actor.space.slug != query.spaceSlug) {
      return null;
    }
    return query.copyWith(spaceId: actor.space.id);
  } on FormatException {
    return null;
  }
}

String _contextualItemRoute(
  String family,
  String id,
  DiscoveryQuery query,
) => Uri(
  path:
      '/discover/items/${Uri.encodeComponent(family)}/${Uri.encodeComponent(id)}',
  queryParameters: query.isSpace
      ? {'context': 'space', 'space': query.spaceSlug!}
      : null,
).toString();

StatefulShellBranch discoveryBranch(AppRuntime runtime) => StatefulShellBranch(
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
            onOpenActivity: (id) => context.push('/activities/$id'),
            onOpenItem: (family, id) =>
                context.push('/discover/items/$family/$id'),
          ),
        );
      },
    ),
  ],
);

List<RouteBase> discoveryRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/discover/search',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final discovery = runtime.discovery;
      if (discovery == null) {
        return const MakoloSecondaryScreen(
          title: 'Rechercher',
          message: 'La recherche n’est pas disponible pour le moment.',
        );
      }
      final query = _routeQuery(state.uri.queryParameters, runtime);
      if (query == null) {
        return const MakoloSecondaryScreen(
          title: 'Recherche',
          message: 'Ces critères sont invalides. Revenez à Découvrir pour les modifier.',
        );
      }
      return DiscoverySearchScreen(
        key: ValueKey(state.uri.toString()),
        initialQuery: query,
        repository: discovery,
        location: runtime.location,
        geoSearch: runtime.geoSearch,
        onOpenActivity: (id) => context.push(
          query.isSpace
              ? _contextualItemRoute('activity', id, query)
              : '/activities/$id',
        ),
        onOpenItem: (family, id) =>
            context.push(_contextualItemRoute(family, id, query)),
      );
    },
  ),
  GoRoute(
    path: '/discover/map',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final discovery = runtime.discovery;
      if (discovery == null) {
        return const MakoloSecondaryScreen(
          title: 'Carte',
          message: 'La carte n’est pas disponible pour le moment.',
        );
      }
      final query = _routeQuery(state.uri.queryParameters, runtime);
      if (query == null) {
        return const MakoloSecondaryScreen(
          title: 'Carte',
          message:
              'Impossible d’ouvrir cette recherche. Revenez aux résultats.',
        );
      }
      return DiscoveryMapScreen(
        key: ValueKey(state.uri.toString()),
        query: query,
        initialSelectedCandidateKey: state.uri.queryParameters['selected'],
        repository: discovery,
        authenticated: runtime.isAuthenticated,
        mapConfig: runtime.mapConfig,
        location: runtime.location,
        geoSearch: runtime.geoSearch,
        onOpenOccurrence: (id) {
          // A Space occurrence cannot silently navigate into personal owner
          // entitlements. The contextual item callback owns Space N3.
          if (!query.isSpace) context.push('/occurrences/$id');
        },
        onOpenItem: (family, id) async {
          await context.push<void>(_contextualItemRoute(family, id, query));
        },
      );
    },
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
        onOpenItem: (family, id) => context.push('/discover/items/$family/$id'),
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
      final actorQuery = _routeQuery(state.uri.queryParameters, runtime);
      if (actorQuery == null) {
        return const MakoloSecondaryScreen(
          title: 'Possibilité',
          message: 'Ce contexte de découverte n’est plus accessible.',
        );
      }
      return DiscoveryItemDetailScreen(
        key: ValueKey(
          'discover-n3-${actorQuery.spaceId ?? 'personal'}-'
          '${state.pathParameters['family']}-${state.pathParameters['id']}',
        ),
        family: state.pathParameters['family']!,
        id: state.pathParameters['id']!,
        repository: discovery,
        actorQuery: actorQuery,
        authenticated: runtime.isAuthenticated,
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
        key: ValueKey('discover-activity-${state.pathParameters['id']}'),
        activityId: state.pathParameters['id']!,
        repository: discovery,
        conversations: runtime.conversations,
        onOpenConversation: (id) => context.push('/conversations/$id'),
        onOpenOccurrence: (id) =>
            context.push('/occurrences/${Uri.encodeComponent(id)}'),
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
          message: 'Cette occurrence n’est pas disponible sur cet appareil.',
        );
      }
      final occurrenceId = state.pathParameters['id']!;
      return OccurrenceDetailScreen(
        key: ValueKey('discover-occurrence-$occurrenceId'),
        occurrenceId: occurrenceId,
        repository: discovery,
        conversations: runtime.conversations,
        onOpenConversation: (id) => context.push('/conversations/$id'),
        onOpenActivity: (id) =>
            context.push('/activities/${Uri.encodeComponent(id)}'),
        onOpenDayOf: () => context.push(
          '/occurrences/${Uri.encodeComponent(occurrenceId)}/day-of',
        ),
      );
    },
  ),
];
