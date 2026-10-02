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

class _MemoryPreferencesController extends AppPreferencesController {
  _MemoryPreferencesController()
      : super(
          store: FileLaunchPreferencesStore.forFile(File('unused')),
          initial: const LaunchPreferencesSnapshot(),
        );

  LaunchPreferencesSnapshot _snapshot = const LaunchPreferencesSnapshot();

  @override
  LaunchPreferencesSnapshot get value => _snapshot;

  @override
  Future<void> setThemePreference(MakoloThemePreference value) async {
    _snapshot = _snapshot.copyWith(themePreference: value);
    notifyListeners();
  }

  @override
  Future<void> setReduceMotion(bool value) async {
    _snapshot = _snapshot.copyWith(reduceMotion: value);
    notifyListeners();
  }
}

void main() {
  test('theme and Reduce Motion persist across store reopen', () async {
    final controller = _MemoryPreferencesController();
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

    expect(find.text('Système'), findsOneWidget);
    expect(find.text('Clair'), findsOneWidget);
    expect(find.text('Sombre'), findsOneWidget);
    expect(find.text('Réduire les animations'), findsOneWidget);
    expect(find.text('Licences'), findsOneWidget);
    expect(find.text('Passkey'), findsNothing);
    expect(find.text('2FA'), findsNothing);
    expect(find.text('Langue'), findsNothing);

    await tester.tap(find.text('Sombre'));
    await tester.pump();
    expect(controller.value.themePreference, MakoloThemePreference.dark);

    await tester.tap(find.byType(Switch));
    await tester.pump();
    expect(controller.value.reduceMotion, isTrue);
  });
}
