import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'day_of_screen.dart';

List<RouteBase> dayOfRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/occurrences/:id/day-of',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.dayOf;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Jour J',
          message: 'Le Jour J n’est pas disponible sur cet appareil.',
        );
      }
      return DayOfScreen(
        occurrenceId: state.pathParameters['id']!,
        repository: repository,
        onOpenAccess: (accessId, detailPath) =>
            context.push('/accesses/$accessId'),
        onPresentCredential: (accessId, credentialPath) => context.push(
          '/accesses/$accessId/credential',
          extra: credentialPath,
        ),
        onOpenLive: (livePath) =>
            context.push('/occurrences/${state.pathParameters['id']}/live'),
      );
    },
  ),
];
