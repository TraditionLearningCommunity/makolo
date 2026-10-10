import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import 'now_screen.dart';

StatefulShellBranch nowBranch(AppRuntime runtime) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: '/now',
      builder: (context, state) => NowScreen(
        repository: runtime.personal!,
        api: runtime.api,
        profileId: runtime.session?.profileId,
        sync: runtime.sync,
      ),
    ),
  ],
);
