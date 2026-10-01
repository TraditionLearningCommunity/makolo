import 'package:flutter/material.dart';

import '../../app/environment.dart';
import '../../app/launch_preferences.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';

class AppSettingsScreen extends StatelessWidget {
  const AppSettingsScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  String _themeLabel(MakoloThemePreference preference) {
    return switch (preference) {
      MakoloThemePreference.system => 'Système',
      MakoloThemePreference.light => 'Clair',
      MakoloThemePreference.dark => 'Sombre',
    };
  }

  @override
  Widget build(BuildContext context) {
    final preferences = runtime.preferences;
    if (preferences == null) {
      return const Scaffold(
        appBar: AppBar(title: Text('Paramètres')),
        body: Center(child: Text('Paramètres indisponibles pour le moment.')),
      );
    }

    return ListenableBuilder(
      listenable: preferences,
      builder: (context, _) {
        final value = preferences.value;
        return Scaffold(
          appBar: AppBar(title: const Text('Paramètres')),
          body: ListView(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.inner,
              MakoloSpacing.md,
              MakoloSpacing.inner,
              MakoloSpacing.xl,
            ),
            children: [
              Text(
                'Apparence',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              Semantics(
                label: 'Apparence ${_themeLabel(value.themePreference)}',
                child: SegmentedButton<MakoloThemePreference>(
                  segments: const [
                    ButtonSegment(
                      value: MakoloThemePreference.system,
                      label: Text('Système'),
                      icon: Icon(Icons.settings_suggest_outlined),
                    ),
                    ButtonSegment(
                      value: MakoloThemePreference.light,
                      label: Text('Clair'),
                      icon: Icon(Icons.light_mode_outlined),
                    ),
                    ButtonSegment(
                      value: MakoloThemePreference.dark,
                      label: Text('Sombre'),
                      icon: Icon(Icons.dark_mode_outlined),
                    ),
                  ],
                  selected: {value.themePreference},
                  onSelectionChanged: (selection) {
                    if (selection.isEmpty) return;
                    preferences.setThemePreference(selection.first);
                  },
                ),
              ),
              const SizedBox(height: MakoloSpacing.xl),
              Text(
                'Accessibilité',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Réduire les animations'),
                subtitle: const Text(
                  'Limite les animations non essentielles. Les réglages du système restent respectés.',
                ),
                value: value.reduceMotion,
                onChanged: preferences.setReduceMotion,
              ),
              const SizedBox(height: MakoloSpacing.lg),
              const Divider(),
              const SizedBox(height: MakoloSpacing.md),
              Text(
                'À propos',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.apps_outlined),
                title: Text('Makolo'),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.description_outlined),
                title: const Text('Licences'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => showLicensePage(
                  context: context,
                  applicationName: 'Makolo',
                ),
              ),
              if (runtime.config?.environment == MakoloRuntimeEnvironment.dev)
                const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.science_outlined),
                  title: Text('Version de développement'),
                  subtitle: Text('Environnement DEV'),
                ),
            ],
          ),
        );
      },
    );
  }
}
