import 'package:go_router/go_router.dart';

import '../app/runtime/app_runtime.dart';
import '../features/settings/notification_preferences_screen.dart' as settings;
import '../navigation/secondary_screen.dart';
import 'notification_screens.dart';

List<RouteBase> notificationRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/settings/notifications',
    builder: (context, state) {
      final repository = runtime.notifications;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Notifications',
          message: 'Les préférences ne sont pas disponibles dans ce contexte.',
        );
      }
      return settings.NotificationPreferencesScreen(
        runtime: runtime,
        repository: repository,
      );
    },
  ),
  GoRoute(
    path: '/notifications',
    builder: (context, state) {
      final repository = runtime.notifications;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Notifications',
          message:
              'Les notifications ne sont pas disponibles dans ce contexte.',
        );
      }
      return NotificationInboxScreen(
        runtime: runtime,
        repository: repository,
        onOpenDestination: (path) async {
          await context.push<Object?>(path);
        },
      );
    },
  ),
];
