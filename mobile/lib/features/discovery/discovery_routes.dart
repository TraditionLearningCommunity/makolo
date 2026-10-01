import 'package:go_router/go_router.dart';

import '../../app/environment.dart';
import '../../app/runtime/app_runtime.dart';
import '../../navigation/refresh_boundary.dart';
import '../../navigation/secondary_screen.dart';
import '../personal/placeholder_screen.dart';
import 'discovery_screens.dart';
import 'discovery_watch_screens.dart';

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
      final discovery = runtime.discovery;
      if (discovery == null) {
        return const MakoloSecondaryScreen(
          title: 'Rechercher',
          message: 'La recherche n’est pas disponible pour le moment.',
        );
      }
      return DiscoverySearchScreen(
        repository: discovery,
        location: runtime.location,
        onOpenActivity: (id) => context.push('/activities/$id'),
        onOpenItem: (family, id) =>
            context.push('/discover/items/$family/$id'),
      );
    },
  ),
  GoRoute(
    path: '/discover/map',
    builder: (context, state) {
      final discovery = runtime.discovery;
      if (discovery == null) {
        return const MakoloSecondaryScreen(
          title: 'Carte',
          message: 'La carte n’est pas disponible pour le moment.',
        );
      }
      final maps =
          runtime.config?.maps ??
          const MakoloMapsConfig(enabled: false, style: null);
      return DiscoveryMapScreen(
        repository: discovery,
        mapConfig: maps,
        onOpenOccurrence: (id) => context.push('/occurrences/$id'),
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
          message: 'Cette occurrence n’est pas disponible sur cet appareil.',
        );
      }
      final occurrenceId = state.pathParameters['id']!;
      return OccurrenceDetailScreen(
        occurrenceId: occurrenceId,
        repository: discovery,
        onOpenActivity: (id) => context.push('/activities/$id'),
        onOpenDayOf: () => context.push('/occurrences/$occurrenceId/day-of'),
      );
    },
  ),
];
