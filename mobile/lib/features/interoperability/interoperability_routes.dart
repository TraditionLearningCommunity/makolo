import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/refresh_boundary.dart';
import 'connections_screen.dart';

List<RouteBase> interoperabilityRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/connections',
    builder: (context, state) => MakoloRefreshBoundary(
      child: ProfileConnectionsScreen(runtime: runtime),
    ),
  ),
];
