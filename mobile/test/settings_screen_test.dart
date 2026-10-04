import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/features/settings/settings_screen.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'fakes.dart';

void main() {
  test('theme and Reduce Motion persist across store reopen', () async {
    final directory = await Directory.systemTemp.createTemp(
      'makolo-settings-test-',
    );
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/preferences.json');

    final first = FileLaunchPreferencesStore.forFile(file);
    await first.setThemePreference(MakoloThemePreference.dark);
    await first.setReduceMotion(true);

    final reopened = FileLaunchPreferencesStore.forFile(file);
    final snapshot = await reopened.read();

    expect(snapshot.themePreference, MakoloThemePreference.dark);
    expect(snapshot.reduceMotion, isTrue);
  });


  testWidgets('appearance control stays usable with larger text', (
    tester,
  ) async {
    final controller = AppPreferencesController(
      store: FileLaunchPreferencesStore.forFile(File('unused-large-text')),
      initial: const LaunchPreferencesSnapshot(),
    );
    addTearDown(controller.dispose);

    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
      preferences: controller,
      config: MakoloRuntimeConfig.fromValues(const {}),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
          child: AppSettingsScreen(
            runtime: runtime,
            packageInfo: Future.value(
              PackageInfo(
                appName: 'Makolo',
                packageName: 'com.makolo.mobile',
                version: '1.0.0',
                buildNumber: '1',
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('Système'), findsOneWidget);
    expect(find.text('Clair'), findsOneWidget);
    expect(find.text('Sombre'), findsOneWidget);
  });

  testWidgets('settings expose active local controls only', (tester) async {
    final controller = AppPreferencesController(
      store: FileLaunchPreferencesStore.forFile(File('unused')),
      initial: const LaunchPreferencesSnapshot(),
    );
    addTearDown(controller.dispose);

    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
      preferences: controller,
      config: MakoloRuntimeConfig.fromValues(const {}),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppSettingsScreen(
          runtime: runtime,
          packageInfo: Future.value(
            PackageInfo(
              appName: 'Makolo',
              packageName: 'com.makolo.mobile',
              version: '1.0.0',
              buildNumber: '1',
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Système'), findsOneWidget);
    expect(find.text('Clair'), findsOneWidget);
    expect(find.text('Sombre'), findsOneWidget);
    expect(find.text('Réduire les animations'), findsOneWidget);
    expect(find.text('Informations légales'), findsOneWidget);
    expect(find.text('Licences open source'), findsNothing);

    await tester.tap(find.text('Informations légales'));
    await tester.pumpAndSettle();
    expect(find.text('Licences open source'), findsOneWidget);
    expect(find.text('Passkey'), findsNothing);
    expect(find.text('2FA'), findsNothing);
    expect(find.text('Langue'), findsNothing);
  });
}
