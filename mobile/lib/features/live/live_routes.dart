import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'live_screen.dart';

List<RouteBase> liveRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/occurrences/:id/live',
    builder: (context, state) {
      final repository = runtime.live;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Makolo Live',
          message: 'Le Live n’est pas disponible sur cet appareil.',
        );
      }
      return LiveScreen(
        occurrenceId: state.pathParameters['id']!,
        repository: repository,
        onBackToDayOf: () =>
            context.go('/occurrences/${state.pathParameters['id']}/day-of'),
      );
    },
  ),
];
