import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class LaunchPreferencesSnapshot {
  const LaunchPreferencesSnapshot({
    this.hasCompletedOnboarding = false,
    this.lastBrandMomentAt,
  });

  final bool hasCompletedOnboarding;
  final DateTime? lastBrandMomentAt;

  LaunchPreferencesSnapshot copyWith({
    bool? hasCompletedOnboarding,
    DateTime? lastBrandMomentAt,
  }) {
    return LaunchPreferencesSnapshot(
      hasCompletedOnboarding:
          hasCompletedOnboarding ?? this.hasCompletedOnboarding,
      lastBrandMomentAt: lastBrandMomentAt ?? this.lastBrandMomentAt,
    );
  }

  Map<String, dynamic> toJson() => {
    'has_completed_onboarding': hasCompletedOnboarding,
    'last_brand_moment_at': lastBrandMomentAt?.toUtc().toIso8601String(),
  };

  static LaunchPreferencesSnapshot fromJson(Map<String, dynamic> json) {
    final rawBrandMomentAt = json['last_brand_moment_at']?.toString();
    return LaunchPreferencesSnapshot(
      hasCompletedOnboarding: json['has_completed_onboarding'] == true,
      lastBrandMomentAt: rawBrandMomentAt == null
          ? null
          : DateTime.tryParse(rawBrandMomentAt)?.toUtc(),
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

  Future<void> _write(LaunchPreferencesSnapshot snapshot) async {
    await _file.parent.create(recursive: true);
    await _file.writeAsString(jsonEncode(snapshot.toJson()), flush: true);
  }
}
