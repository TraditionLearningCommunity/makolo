import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';
import 'package:makolo_mobile/runtime/firebase_runtime_bootstrap.dart';
import 'package:makolo_mobile/runtime/runtime_service_status.dart';

class FakeFirebaseRuntime implements FirebaseRuntime {
  FakeFirebaseRuntime({this.failure});

  final Object? failure;
  int calls = 0;

  @override
  Future<void> initialize() async {
    calls += 1;
    if (failure != null) throw failure!;
  }

  @override
  FirebaseMessaging get messaging => throw UnimplementedError();
}

MakoloRuntimeConfig config({required bool firebase}) =>
    MakoloRuntimeConfig.fromValues({
      'MAKOLO_ENVIRONMENT': 'dev',
      'MAKOLO_FIREBASE_ENABLED': firebase.toString(),
    });

void main() {
  test('disabled Firebase does not initialize plugin runtime', () async {
    final fake = FakeFirebaseRuntime();
    final bootstrap = FirebaseRuntimeBootstrap(
      runtime: fake,
      backgroundRegistrar: (_) {},
    );
    final status = await bootstrap.initialize(config(firebase: false));
    expect(status.state, RuntimeServiceState.disabled);
    expect(fake.calls, 0);
  });

  test('enabled Firebase initializes once', () async {
    final fake = FakeFirebaseRuntime();
    final bootstrap = FirebaseRuntimeBootstrap(
      runtime: fake,
      backgroundRegistrar: (_) {},
    );
    expect(
      (await bootstrap.initialize(config(firebase: true))).isReady,
      isTrue,
    );
    expect(
      (await bootstrap.initialize(config(firebase: true))).isReady,
      isTrue,
    );
    expect(fake.calls, 1);
  });

  test('Firebase failure is isolated as failed status', () async {
    final bootstrap = FirebaseRuntimeBootstrap(
      runtime: FakeFirebaseRuntime(failure: StateError('missing config')),
      backgroundRegistrar: (_) {},
    );
    expect(
      (await bootstrap.initialize(config(firebase: true))).state,
      RuntimeServiceState.failed,
    );
  });
}
