import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import 'mark_screen.dart';

List<RouteBase> markRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/mark',
    builder: (context, state) => MarkScreen(runtime: runtime),
  ),
];
