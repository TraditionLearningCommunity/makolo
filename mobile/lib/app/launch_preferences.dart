import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import 'runtime/actor_context.dart';
import 'runtime/actor_context_controller.dart';

enum MakoloThemePreference { system, light, dark }

class LaunchPreferencesSnapshot {
  const LaunchPreferencesSnapshot({
    this.hasCompletedOnboarding = false,
    this.lastBrandMomentAt,
    this.themePreference = MakoloThemePreference.system,
    this.reduceMotion = false,
    this.actorContexts = const {},
    this.shellLocations = const {},
  });

  final bool hasCompletedOnboarding;
  final DateTime? lastBrandMomentAt;
  final MakoloThemePreference themePreference;
  final bool reduceMotion;
  final Map<String, ActorContext> actorContexts;
  final Map<String, String> shellLocations;

  LaunchPreferencesSnapshot copyWith({
    bool? hasCompletedOnboarding,
    DateTime? lastBrandMomentAt,
    MakoloThemePreference? themePreference,
    bool? reduceMotion,
    Map<String, ActorContext>? actorContexts,
    Map<String, String>? shellLocations,
  }) {
    return LaunchPreferencesSnapshot(
      hasCompletedOnboarding:
          hasCompletedOnboarding ?? this.hasCompletedOnboarding,
      lastBrandMomentAt: lastBrandMomentAt ?? this.lastBrandMomentAt,
      themePreference: themePreference ?? this.themePreference,
      reduceMotion: reduceMotion ?? this.reduceMotion,
      actorContexts: actorContexts ?? this.actorContexts,
      shellLocations: shellLocations ?? this.shellLocations,
    );
  }

  Map<String, dynamic> toJson() => {
    'has_completed_onboarding': hasCompletedOnboarding,
    'last_brand_moment_at': lastBrandMomentAt?.toUtc().toIso8601String(),
    'theme': themePreference.name,
    'reduce_motion': reduceMotion,
    'actor_contexts': {
      for (final entry in actorContexts.entries)
        entry.key: ActorContextCodec.encode(entry.value),
    },
    'shell_locations': shellLocations,
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

    final actorContexts = <String, ActorContext>{};
    final rawActorContexts = json['actor_contexts'];
    if (rawActorContexts is Map) {
      for (final entry in rawActorContexts.entries) {
        final profileId = entry.key;
        if (profileId is! String || profileId.trim().isEmpty) continue;
        final context = ActorContextCodec.decode(entry.value);
        if (context != null) {
          actorContexts[profileId] = context;
        }
      }
    }

    final shellLocations = <String, String>{};
    final rawShellLocations = json['shell_locations'];
    if (rawShellLocations is Map) {
      for (final entry in rawShellLocations.entries) {
        final profileId = entry.key;
        final location = entry.value;
        if (profileId is! String || profileId.trim().isEmpty) continue;
        if (location is! String || !_validShellLocation(location)) continue;
        shellLocations[profileId] = location;
      }
    }

    return LaunchPreferencesSnapshot(
      hasCompletedOnboarding: json['has_completed_onboarding'] == true,
      lastBrandMomentAt: rawBrandMomentAt == null
          ? null
          : DateTime.tryParse(rawBrandMomentAt)?.toUtc(),
      themePreference: theme ?? MakoloThemePreference.system,
      reduceMotion: json['reduce_motion'] == true,
      actorContexts: actorContexts,
      shellLocations: shellLocations,
    );
  }

  static bool _validShellLocation(String value) {
    final uri = Uri.tryParse(value);
    return uri != null && uri.path.startsWith('/') && uri.host.isEmpty;
  }
}

abstract interface class LaunchPreferencesStore {
  Future<LaunchPreferencesSnapshot> read();
  Future<void> setOnboardingCompleted();
  Future<void> setLastBrandMomentAt(DateTime value);
}

class FileLaunchPreferencesStore
    implements LaunchPreferencesStore, ActorContextStore {
  FileLaunchPreferencesStore._(this._file);

  static const _fileName = 'makolo-launch-preferences-v1.json';
  static final Map<String, Future<void>> _writeTails = <String, Future<void>>{};

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
    final pending = _writeTails[_file.absolute.path];
    if (pending != null) {
      await pending;
    }
    return _readCurrent();
  }

  @override
  Future<void> setOnboardingCompleted() {
    return _mutate(
      (current) => current.copyWith(hasCompletedOnboarding: true),
    );
  }

  @override
  Future<void> setLastBrandMomentAt(DateTime value) {
    return _mutate(
      (current) => current.copyWith(lastBrandMomentAt: value.toUtc()),
    );
  }

  Future<void> setThemePreference(MakoloThemePreference value) {
    return _mutate((current) => current.copyWith(themePreference: value));
  }

  Future<void> setReduceMotion(bool value) {
    return _mutate((current) => current.copyWith(reduceMotion: value));
  }

  @override
  Future<ActorContext> readActorContext(String profileId) async {
    final current = await read();
    return current.actorContexts[profileId] ?? const PersonalActorContext();
  }

  @override
  Future<void> writeActorContext(String profileId, ActorContext context) {
    return _mutate((current) {
      final contexts = <String, ActorContext>{
        ...current.actorContexts,
        profileId: context,
      };
      return current.copyWith(actorContexts: contexts);
    });
  }

  @override
  Future<void> removeActorContext(String profileId) {
    return _mutate((current) {
      if (!current.actorContexts.containsKey(profileId)) return null;
      final contexts = <String, ActorContext>{...current.actorContexts}
        ..remove(profileId);
      return current.copyWith(actorContexts: contexts);
    });
  }

  Future<String?> readShellLocation(String profileId) async {
    final current = await read();
    return current.shellLocations[profileId];
  }

  Future<void> writeShellLocation(String profileId, String location) {
    if (!LaunchPreferencesSnapshot._validShellLocation(location)) {
      return Future<void>.value();
    }
    return _mutate((current) {
      if (current.shellLocations[profileId] == location) return null;
      final locations = <String, String>{
        ...current.shellLocations,
        profileId: location,
      };
      return current.copyWith(shellLocations: locations);
    });
  }

  Future<void> removeShellLocation(String profileId) {
    return _mutate((current) {
      if (!current.shellLocations.containsKey(profileId)) return null;
      final locations = <String, String>{...current.shellLocations}
        ..remove(profileId);
      return current.copyWith(shellLocations: locations);
    });
  }

  Future<void> _mutate(
    LaunchPreferencesSnapshot? Function(LaunchPreferencesSnapshot current)
        update,
  ) {
    final key = _file.absolute.path;
    final previous = _writeTails[key] ?? Future<void>.value();
    final operation = previous.then((_) async {
      final current = await _readCurrent();
      final next = update(current);
      if (next == null) return;
      await _writeCurrent(next);
    });
    _writeTails[key] = operation.then<void>(
      (_) {},
      onError: (Object _, StackTrace __) {},
    );
    return operation;
  }

  Future<LaunchPreferencesSnapshot> _readCurrent() async {
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

  Future<void> _writeCurrent(LaunchPreferencesSnapshot snapshot) async {
    await _file.parent.create(recursive: true);
    await _file.writeAsString(jsonEncode(snapshot.toJson()), flush: true);
  }
}

class AppPreferencesController extends ChangeNotifier {
  AppPreferencesController({
    required this._store,
    required LaunchPreferencesSnapshot initial,
  }) : _value = initial;

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
