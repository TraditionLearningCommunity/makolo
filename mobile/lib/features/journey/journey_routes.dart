import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'journey_detail_screen.dart';

String? _ownerResourceId(String link, String collection) {
  final uri = Uri.tryParse(link);
  if (uri == null) return null;
  final segments = uri.pathSegments;
  final index = segments.indexOf(collection);
  if (index < 0 || index + 1 >= segments.length) return null;
  final id = segments[index + 1].trim();
  return id.isEmpty ? null : id;
}

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
            context.push('/journeys/$journeyId/forms/${form.id}', extra: form),
        onOpenRequirement: (requirement) => context.push(
          '/journeys/$journeyId/requirements/${requirement.id}',
          extra: requirement,
        ),
        onOpenResources: (resourcesLink) => context.push(
          '/journeys/$journeyId/resources',
          extra: resourcesLink,
        ),
        onOpenActivity: (activity) {
          if (activity.link == null || activity.id.isEmpty) return;
          context.push('/activities/${activity.id}');
        },
        onOpenOccurrence: (occurrence) {
          if (occurrence.link == null || occurrence.id.isEmpty) return;
          context.push('/occurrences/${occurrence.id}');
        },
        onOpenAccess: (access) {
          if (access.link == null || access.id.isEmpty) return;
          context.push('/accesses/${access.id}');
        },
        onOpenDayOf: (dayOfLink) {
          final occurrenceId = _ownerResourceId(dayOfLink, 'occurrences');
          if (occurrenceId != null) {
            context.push('/occurrences/$occurrenceId/day-of');
          }
        },
        onOpenLive: (liveLink) {
          final occurrenceId = _ownerResourceId(liveLink, 'occurrences');
          if (occurrenceId != null) {
            context.push('/occurrences/$occurrenceId/live');
          }
        },
      );
    },
  ),
];
