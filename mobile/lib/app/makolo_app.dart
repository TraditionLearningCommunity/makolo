import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../design/behavior_states.dart';
import '../design/makolo_theme.dart';
import '../design/system_ui.dart';
import '../features/splash/splash_screen.dart';
import '../runtime/runtime_ingress_listener.dart';
import '../runtime/runtime_providers.dart';
import 'launch_gate.dart';
import 'launch_preferences.dart';
import 'providers.dart';
import 'router.dart';
import 'sync_lifecycle.dart';

final DateTime _makoloLaunchStartedAt = DateTime.now();

class MakoloApp extends ConsumerWidget {
  const MakoloApp({super.key});

  ThemeMode _themeMode(MakoloThemePreference preference) {
    return switch (preference) {
      MakoloThemePreference.system => ThemeMode.system,
      MakoloThemePreference.light => ThemeMode.light,
      MakoloThemePreference.dark => ThemeMode.dark,
    };
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final runtime = ref.watch(appRuntimeProvider);

    return runtime.when(
      loading: () => MaterialApp(
        title: 'Makolo',
        debugShowCheckedModeBanner: false,
        theme: buildMakoloLightTheme(),
        darkTheme: buildMakoloDarkTheme(),
        themeMode: ThemeMode.system,
        home: const MakoloSystemUi(child: SplashScreen()),
      ),
      error: (error, stackTrace) => MaterialApp(
        title: 'Makolo',
        debugShowCheckedModeBanner: false,
        theme: buildMakoloLightTheme(),
        darkTheme: buildMakoloDarkTheme(),
        themeMode: ThemeMode.system,
        home: MakoloSystemUi(
          child: Scaffold(
            body: MakoloErrorState(
              message:
                  'Makolo n’a pas pu ouvrir les données locales de cet appareil.',
              preservedMessage:
                  'Aucune donnée locale n’a été supprimée. Vous pouvez réessayer.',
              onRetry: () => ref.invalidate(appRuntimeProvider),
            ),
          ),
        ),
      ),
      data: (runtime) {
        final ingress = ref.watch(runtimeIngressProvider);
        final router = createMakoloRouter(
          runtime,
          onAuthenticationChanged: () => ref.invalidate(appRuntimeProvider),
        );

        Widget buildConfiguredApp(LaunchPreferencesSnapshot preferences) {
          return MaterialApp.router(
            title: 'Makolo',
            debugShowCheckedModeBanner: false,
            theme: buildMakoloLightTheme(),
            darkTheme: buildMakoloDarkTheme(),
            themeMode: _themeMode(preferences.themePreference),
            routerConfig: router,
            builder: (context, child) {
              Widget routedChild = child ?? const SizedBox.shrink();

              if (runtime.isAuthenticated) {
                routedChild = SyncLifecycle(
                  runtime: runtime,
                  onSessionExpired: () {
                    runtime.recovery.markSessionExpired();
                    ref.invalidate(appRuntimeProvider);
                  },
                  child: routedChild,
                );
              }

              Widget launched = MakoloSystemUi(
                child: LaunchGate(
                  runtime: runtime,
                  router: router,
                  launchStartedAt: _makoloLaunchStartedAt,
                  child: routedChild,
                ),
              );

              if (preferences.reduceMotion) {
                launched = MediaQuery(
                  data: MediaQuery.of(
                    context,
                  ).copyWith(disableAnimations: true),
                  child: launched,
                );
              }

              if (ingress == null) return launched;
              return RuntimeIngressListener(
                ingress: ingress,
                runtime: runtime,
                router: router,
                child: launched,
              );
            },
          );
        }

        final preferences = runtime.preferences;
        if (preferences == null) {
          return buildConfiguredApp(const LaunchPreferencesSnapshot());
        }
        return ListenableBuilder(
          listenable: preferences,
          builder: (context, _) => buildConfiguredApp(preferences.value),
        );
      },
    );
  }
}
