import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

enum MakoloThemePreference { system, light, dark }

class LaunchPreferencesSnapshot {
  const LaunchPreferencesSnapshot({
    this.hasCompletedOnboarding = false,
    this.lastBrandMomentAt,
    this.themePreference = MakoloThemePreference.system,
    this.reduceMotion = false,
  });

  final bool hasCompletedOnboarding;
  final DateTime? lastBrandMomentAt;
  final MakoloThemePreference themePreference;
  final bool reduceMotion;

  LaunchPreferencesSnapshot copyWith({
    bool? hasCompletedOnboarding,
    DateTime? lastBrandMomentAt,
    MakoloThemePreference? themePreference,
    bool? reduceMotion,
  }) {
    return LaunchPreferencesSnapshot(
      hasCompletedOnboarding:
          hasCompletedOnboarding ?? this.hasCompletedOnboarding,
      lastBrandMomentAt: lastBrandMomentAt ?? this.lastBrandMomentAt,
      themePreference: themePreference ?? this.themePreference,
      reduceMotion: reduceMotion ?? this.reduceMotion,
    );
  }

  Map<String, dynamic> toJson() => {
    'has_completed_onboarding': hasCompletedOnboarding,
    'last_brand_moment_at': lastBrandMomentAt?.toUtc().toIso8601String(),
    'theme': themePreference.name,
    'reduce_motion': reduceMotion,
  };

  static LaunchPreferencesSnapshot fromJson(Map<String, dynamic> json) {
    final rawBrandMomentAt = json['last_brand_moment_at']?.toString();
    final rawTheme = json['theme']?.toString();
    MakoloThemePreference? theme;
    for (final candidate in MakoloThemePreference.values) {
      if (candidate.name == rawTheme) {
        theme = candidate;
        break;
      }
    }
    return LaunchPreferencesSnapshot(
      hasCompletedOnboarding: json['has_completed_onboarding'] == true,
      lastBrandMomentAt: rawBrandMomentAt == null
          ? null
          : DateTime.tryParse(rawBrandMomentAt)?.toUtc(),
      themePreference: theme ?? MakoloThemePreference.system,
      reduceMotion: json['reduce_motion'] == true,
    );
  }
}

abstract interface class LaunchPreferencesStore {
  Future<LaunchPreferencesSnapshot> read();
  Future<void> setOnboardingCompleted();
  Future<void> setLastBrandMomentAt(DateTime value);
}

class FileLaunchPreferencesStore implements LaunchPreferencesStore {
  FileLaunchPreferencesStore._(this._file);

  static const _fileName = 'makolo-launch-preferences-v1.json';

  final File _file;

  static Future<FileLaunchPreferencesStore> open() async {
    final directory = await getApplicationSupportDirectory();
    return FileLaunchPreferencesStore._(
      File('${directory.path}${Platform.pathSeparator}$_fileName'),
    );
  }

  @visibleForTesting
  static FileLaunchPreferencesStore forFile(File file) {
    return FileLaunchPreferencesStore._(file);
  }

  @override
  Future<LaunchPreferencesSnapshot> read() async {
    if (!await _file.exists()) {
      return const LaunchPreferencesSnapshot();
    }

    try {
      final raw = await _file.readAsString();
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) {
        return const LaunchPreferencesSnapshot();
      }
      return LaunchPreferencesSnapshot.fromJson(decoded);
    } on Object {
      return const LaunchPreferencesSnapshot();
    }
  }

  @override
  Future<void> setOnboardingCompleted() async {
    final current = await read();
    await _write(current.copyWith(hasCompletedOnboarding: true));
  }

  @override
  Future<void> setLastBrandMomentAt(DateTime value) async {
    final current = await read();
    await _write(current.copyWith(lastBrandMomentAt: value.toUtc()));
  }

  Future<void> setThemePreference(MakoloThemePreference value) async {
    final current = await read();
    await _write(current.copyWith(themePreference: value));
  }

  Future<void> setReduceMotion(bool value) async {
    final current = await read();
    await _write(current.copyWith(reduceMotion: value));
  }

  Future<void> _write(LaunchPreferencesSnapshot snapshot) async {
    await _file.parent.create(recursive: true);
    await _file.writeAsString(jsonEncode(snapshot.toJson()), flush: true);
  }
}

class AppPreferencesController extends ChangeNotifier {
  AppPreferencesController({
    required FileLaunchPreferencesStore store,
    required LaunchPreferencesSnapshot initial,
  }) : this._store = store,
       _value = initial;

  final FileLaunchPreferencesStore _store;
  LaunchPreferencesSnapshot _value;

  LaunchPreferencesSnapshot get value => _value;

  Future<void> setThemePreference(MakoloThemePreference value) async {
    if (_value.themePreference == value) return;
    await _store.setThemePreference(value);
    _value = _value.copyWith(themePreference: value);
    notifyListeners();
  }

  Future<void> setReduceMotion(bool value) async {
    if (_value.reduceMotion == value) return;
    await _store.setReduceMotion(value);
    _value = _value.copyWith(reduceMotion: value);
    notifyListeners();
  }
}
