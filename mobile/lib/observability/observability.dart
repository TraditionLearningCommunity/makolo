import 'package:sentry_flutter/sentry_flutter.dart';

const _sensitiveKeyFragments = {
  'authorization',
  'password',
  'secret',
  'token',
  'credential',
  'qr',
  'payload',
  'document',
  'file_path',
  'filepath',
  'accesscredential',
  'refresh_token',
  'jwt',
};

Map<String, String> safeDiagnosticTags(Map<String, Object?> tags) {
  final safe = <String, String>{};
  for (final entry in tags.entries) {
    final key = entry.key.toLowerCase();
    if (_sensitiveKeyFragments.any(key.contains)) continue;
    final value = entry.value?.toString();
    if (value == null || value.length > 120) continue;
    safe[entry.key] = value;
  }
  return safe;
}

abstract interface class CrashReporter {
  Future<void> report(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?> tags = const {},
  });
}

class NoopCrashReporter implements CrashReporter {
  const NoopCrashReporter();

  @override
  Future<void> report(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?> tags = const {},
  }) async {}
}

class SentryCrashReporter implements CrashReporter {
  const SentryCrashReporter();

  @override
  Future<void> report(
    Object error,
    StackTrace stackTrace, {
    Map<String, Object?> tags = const {},
  }) async {
    final safeTags = safeDiagnosticTags(tags);
    await Sentry.captureException(
      error,
      stackTrace: stackTrace,
      withScope: (scope) {
        for (final entry in safeTags.entries) {
          scope.setTag(entry.key, entry.value);
        }
      },
    );
  }
}

abstract interface class Diagnostics {
  void event(String name, {Map<String, Object?> tags = const {}});
}

class NoopDiagnostics implements Diagnostics {
  const NoopDiagnostics();

  @override
  void event(String name, {Map<String, Object?> tags = const {}}) {}
}
