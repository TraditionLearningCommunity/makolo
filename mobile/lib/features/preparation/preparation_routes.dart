import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import '../../platform/sharing/share_gateway.dart';
import '../journey/journey_selector.dart';
import 'preparation_resources_screen.dart';
import 'requirement_detail_screen.dart';

List<RouteBase> preparationRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/journeys/:journeyId/requirements/:assessmentId',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.requirements;
      if (repository == null) {
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
        repository: repository,
      );
    },
  ),
  GoRoute(
    path: '/journeys/:journeyId/resources',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.preparationResources;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Documents et instructions',
          message: 'Ces ressources ne sont pas disponibles sur cet appareil.',
        );
      }
      return PreparationResourcesScreen(
        journeyId: state.pathParameters['journeyId']!,
        resourcesPath: state.extra is String ? state.extra! as String : null,
        repository: repository,
        onOpenExternal: (url) {
          final uri = Uri.tryParse(url);
          if (uri == null ||
              !uri.hasScheme ||
              !{'http', 'https'}.contains(uri.scheme.toLowerCase())) {
            return Future.value(false);
          }
          return const SystemShareGateway().openExternal(uri);
        },
      );
    },
  ),
];
