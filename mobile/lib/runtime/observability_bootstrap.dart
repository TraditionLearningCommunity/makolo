import 'package:sentry_flutter/sentry_flutter.dart';

import '../app/environment.dart';
import '../observability/observability.dart';
import 'runtime_service_status.dart';

typedef SentryInitializer = Future<void> Function(
  String dsn,
  String environment,
  String? release,
);

Future<void> _initializeSentry(
  String dsn,
  String environment,
  String? release,
) {
  return SentryFlutter.init((options) {
    options
      ..dsn = dsn
      ..environment = environment
      ..release = release
      ..sendDefaultPii = false;
  });
}

class ObservabilityRuntime {
  ObservabilityRuntime({this._initializer = _initializeSentry});

  final SentryInitializer _initializer;
  RuntimeServiceStatus _status = const RuntimeServiceStatus.disabled();
  CrashReporter _reporter = const NoopCrashReporter();

  RuntimeServiceStatus get status => _status;
  CrashReporter get reporter => _reporter;

  Future<RuntimeServiceStatus> initialize(MakoloRuntimeConfig config) async {
    if (!config.sentry.enabled) {
      _reporter = const NoopCrashReporter();
      return _status = const RuntimeServiceStatus.disabled();
    }
    if (_status.isReady) return _status;
    _status = const RuntimeServiceStatus(RuntimeServiceState.initializing);
    try {
      await _initializer(
        config.sentry.dsn!,
        config.environment.name,
        config.sentry.release,
      );
      _reporter = const SentryCrashReporter();
      return _status = const RuntimeServiceStatus.ready();
    } catch (error) {
      _reporter = const NoopCrashReporter();
      return _status = RuntimeServiceStatus.failed(
        error.runtimeType.toString(),
      );
    }
  }
}
