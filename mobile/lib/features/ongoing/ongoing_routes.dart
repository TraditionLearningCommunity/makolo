import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'ongoing_screen.dart';

StatefulShellBranch ongoingBranch(AppRuntime runtime) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: '/ongoing',
      builder: (context, state) => OngoingScreen(repository: runtime.personal!),
    ),
  ],
);

List<RouteBase> ongoingRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/ongoing/calendar',
    builder: (context, state) => const MakoloSecondaryScreen(
      title: 'Calendrier',
      message: 'Aucune date à afficher pour le moment.',
    ),
  ),
];
