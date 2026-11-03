import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import 'ongoing_calendar_screen.dart';
import 'ongoing_screen.dart';

StatefulShellBranch ongoingBranch(AppRuntime runtime) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: '/ongoing',
      builder: (context, state) => OngoingScreen(
        repository: runtime.personal!,
        baseUri: runtime.api?.baseUri,
        api: runtime.api,
        discovery: runtime.discovery,
        initialContinuityId: state.uri.queryParameters['continuity'],
      ),
    ),
  ],
);

List<RouteBase> ongoingRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/ongoing/calendar',
    builder: (context, state) =>
        OngoingCalendarScreen(repository: runtime.personal!, api: runtime.api),
  ),
];
