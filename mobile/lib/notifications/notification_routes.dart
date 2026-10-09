import 'package:go_router/go_router.dart';

import '../app/runtime/app_runtime.dart';
import '../navigation/secondary_screen.dart';
import 'notification_repository.dart';
import 'notification_screens.dart';

List<RouteBase> notificationRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/notifications',
    builder: (context, state) {
      final database = runtime.database;
      final store = runtime.store;
      final profileId = runtime.session?.profileId;
      if (database == null || store == null || profileId == null) {
        return const MakoloSecondaryScreen(
          title: 'Notifications',
          message:
              'Les notifications ne sont pas disponibles dans ce contexte.',
        );
      }
      final repository = NotificationRepository(
        database: database,
        store: store,
        profileId: profileId,
        sync: runtime.sync,
      );
      return NotificationInboxScreen(
        repository: repository,
        onOpenDestination: (path) async {
          await context.push<Object?>(path);
        },
      );
    },
  ),
];
