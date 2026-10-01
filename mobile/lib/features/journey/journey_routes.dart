import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'journey_detail_screen.dart';

List<RouteBase> journeyRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/journeys/:id',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.journeys;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Démarche',
          message: 'Cette démarche n’est pas disponible sur cet appareil.',
        );
      }
      final journeyId = state.pathParameters['id']!;
      return JourneyDetailScreen(
        journeyId: journeyId,
        repository: repository,
        onOpenForm: (form) =>
            context.push('/journeys/' + journeyId + '/forms/' + form.id, extra: form),
        onOpenRequirement: (requirement) => context.push(
          '/journeys/' + journeyId + '/requirements/' + requirement.id,
          extra: requirement,
        ),
        onOpenResources: (resourcesLink) => context.push(
          '/journeys/' + journeyId + '/resources',
          extra: resourcesLink,
        ),
      );
    },
  ),
];
