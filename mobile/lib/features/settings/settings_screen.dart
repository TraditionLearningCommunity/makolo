import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../app/launch_preferences.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';

class AppSettingsScreen extends StatelessWidget {
  const AppSettingsScreen({super.key, required this.runtime, this.packageInfo});

  final AppRuntime runtime;
  final Future<PackageInfo>? packageInfo;

  String _themeLabel(MakoloThemePreference preference) {
    return switch (preference) {
      MakoloThemePreference.system => 'Système',
      MakoloThemePreference.light => 'Clair',
      MakoloThemePreference.dark => 'Sombre',
    };
  }


  void _showLegalInformation(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(
            MakoloSpacing.inner,
            0,
            MakoloSpacing.inner,
            MakoloSpacing.lg,
          ),
          children: [
            Text(
              'Informations légales',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: MakoloSpacing.sm),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.description_outlined),
              title: const Text('Licences open source'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                Navigator.of(sheetContext).pop();
                showLicensePage(
                  context: context,
                  applicationName: 'Makolo',
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final preferences = runtime.preferences;
    if (preferences == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Paramètres')),
        body: const Center(
          child: Text('Paramètres indisponibles pour le moment.'),
        ),
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
              Text('Apparence', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: MakoloSpacing.sm),
              Semantics(
                label: 'Apparence ${_themeLabel(value.themePreference)}',
                child: SegmentedButton<MakoloThemePreference>(
                  segments: const [
                    ButtonSegment(
                      value: MakoloThemePreference.system,
                      label: Text('Système'),
                    ),
                    ButtonSegment(
                      value: MakoloThemePreference.light,
                      label: Text('Clair'),
                    ),
                    ButtonSegment(
                      value: MakoloThemePreference.dark,
                      label: Text('Sombre'),
                    ),
                  ],
                  showSelectedIcon: false,
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
              Text('À propos', style: Theme.of(context).textTheme.titleMedium),
              _AppVersionTile(packageInfo: packageInfo),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.gavel_outlined),
                title: const Text('Informations légales'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _showLegalInformation(context),
              ),
              if (runtime.isDevelopment)
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

class _AppVersionTile extends StatefulWidget {
  const _AppVersionTile({this.packageInfo});

  final Future<PackageInfo>? packageInfo;

  @override
  State<_AppVersionTile> createState() => _AppVersionTileState();
}

class _AppVersionTileState extends State<_AppVersionTile> {
  late final Future<PackageInfo> _packageInfo =
      widget.packageInfo ?? PackageInfo.fromPlatform();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PackageInfo>(
      future: _packageInfo,
      builder: (context, snapshot) {
        final info = snapshot.data;
        final version = info == null
            ? null
            : '${info.version} (${info.buildNumber})';
        return ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.apps_outlined),
          title: const Text('Makolo'),
          subtitle: version == null ? null : Text('Version $version'),
        );
      },
    );
  }
}
