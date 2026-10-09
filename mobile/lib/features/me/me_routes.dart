import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import 'me_screen.dart';

StatefulShellBranch meBranch(AppRuntime runtime) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: '/me',
      builder: (context, state) => MeScreen(
        repository: runtime.personal!,
        onOpenDestination: (destination) {
          if (destination.kind == 'access_collection') {
            context.push('/accesses');
            return true;
          }
          return false;
        },
      ),
    ),
  ],
);
