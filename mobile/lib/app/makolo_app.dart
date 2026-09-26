import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../design/behavior_states.dart';
import '../design/makolo_theme.dart';
import '../features/auth/login_screen.dart';
import '../features/splash/splash_screen.dart';
import 'providers.dart';
import 'router.dart';
import 'sync_lifecycle.dart';

class MakoloApp extends ConsumerWidget {
  const MakoloApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final runtime = ref.watch(appRuntimeProvider);

    return runtime.when(
      loading: () => MaterialApp(
        title: 'Makolo',
        debugShowCheckedModeBanner: false,
        theme: buildMakoloTheme(),
        home: const SplashScreen(),
      ),
      error: (error, stackTrace) => MaterialApp(
        title: 'Makolo',
        debugShowCheckedModeBanner: false,
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: MakoloErrorState(
            message:
                'Makolo n’a pas pu ouvrir les données locales de cet appareil.',
            preservedMessage:
                'Aucune donnée locale n’a été supprimée. Vous pouvez réessayer.',
            onRetry: () => ref.invalidate(appRuntimeProvider),
          ),
        ),
      ),
      data: (runtime) {
        if (!runtime.isAuthenticated) {
          return MaterialApp(
            title: 'Makolo',
            debugShowCheckedModeBanner: false,
            theme: buildMakoloTheme(),
            home: LoginScreen(runtime: runtime),
          );
        }

        return MaterialApp.router(
          title: 'Makolo',
          debugShowCheckedModeBanner: false,
          theme: buildMakoloTheme(),
          routerConfig: createMakoloRouter(runtime),
          builder: (context, child) => SyncLifecycle(
            runtime: runtime,
            child: child ?? const SizedBox.shrink(),
            onSessionExpired: () {
              runtime.recovery.markSessionExpired();
              ref.invalidate(appRuntimeProvider);
            },
          ),
        );
      },
    );
  }
}
