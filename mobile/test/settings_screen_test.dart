import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/features/settings/settings_screen.dart';

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

  testWidgets('settings expose active local controls only', (tester) async {
    final directory = await Directory.systemTemp.createTemp(
      'makolo-settings-widget-',
    );
    addTearDown(() => directory.delete(recursive: true));
    final store = FileLaunchPreferencesStore.forFile(
      File('${directory.path}/preferences.json'),
    );
    final controller = AppPreferencesController(
      store: store,
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
      MaterialApp(home: AppSettingsScreen(runtime: runtime)),
    );

    expect(find.text('Système'), findsOneWidget);
    expect(find.text('Clair'), findsOneWidget);
    expect(find.text('Sombre'), findsOneWidget);
    expect(find.text('Réduire les animations'), findsOneWidget);
    expect(find.text('Licences'), findsOneWidget);
    expect(find.text('Passkey'), findsNothing);
    expect(find.text('2FA'), findsNothing);
    expect(find.text('Langue'), findsNothing);

    await tester.tap(find.text('Sombre'));
    await tester.pumpAndSettle();
    expect(controller.value.themePreference, MakoloThemePreference.dark);

    await tester.tap(find.byType(Switch));
    await tester.pumpAndSettle();
    expect(controller.value.reduceMotion, isTrue);
  });
}
