import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';
import 'package:makolo_mobile/observability/observability.dart';
import 'package:makolo_mobile/runtime/observability_bootstrap.dart';
import 'package:makolo_mobile/runtime/runtime_service_status.dart';

MakoloRuntimeConfig config({required bool sentry}) =>
    MakoloRuntimeConfig.fromValues({
      'MAKOLO_ENVIRONMENT': 'dev',
      'MAKOLO_SENTRY_ENABLED': sentry.toString(),
      if (sentry) 'MAKOLO_SENTRY_DSN': 'https://public@example.invalid/1',
    });

void main() {
  test('disabled Sentry selects Noop without initialization', () async {
    var calls = 0;
    final runtime = ObservabilityRuntime(
      initializer: (_, _, _) async => calls += 1,
    );
    expect(
      (await runtime.initialize(config(sentry: false))).state,
      RuntimeServiceState.disabled,
    );
    expect(runtime.reporter, isA<NoopCrashReporter>());
    expect(calls, 0);
  });

  test('enabled Sentry selects reporter and runtime environment', () async {
    String? environment;
    String? release;
    final runtime = ObservabilityRuntime(
      initializer: (_, value, buildRelease) async {
        environment = value;
        release = buildRelease;
      },
    );
    expect((await runtime.initialize(config(sentry: true))).isReady, isTrue);
    expect(runtime.reporter, isA<SentryCrashReporter>());
    expect(environment, 'dev');
    expect(release, isNull);
  });
}
