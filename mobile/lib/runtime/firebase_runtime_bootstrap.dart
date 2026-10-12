import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import '../app/environment.dart';
import 'runtime_service_status.dart';

@pragma('vm:entry-point')
Future<void> makoloFirebaseBackgroundMessage(RemoteMessage message) async {
  // The background isolate deliberately does not open a Profile database or
  // mutate owner-backed truth. Foreground/resume performs safe acquisition.
  await Firebase.initializeApp();
}

abstract interface class FirebaseRuntime {
  Future<void> initialize();
  FirebaseMessaging get messaging;
}

class PluginFirebaseRuntime implements FirebaseRuntime {
  @override
  Future<void> initialize() => Firebase.initializeApp();

  @override
  FirebaseMessaging get messaging => FirebaseMessaging.instance;
}

typedef BackgroundMessageRegistrar = void Function(
  Future<void> Function(RemoteMessage) handler,
);

class FirebaseRuntimeBootstrap {
  FirebaseRuntimeBootstrap({
    FirebaseRuntime? runtime,
    this._backgroundRegistrar = FirebaseMessaging.onBackgroundMessage,
  }) : _runtime = runtime ?? PluginFirebaseRuntime();

  final FirebaseRuntime _runtime;
  final BackgroundMessageRegistrar _backgroundRegistrar;
  RuntimeServiceStatus _status = const RuntimeServiceStatus.disabled();

  RuntimeServiceStatus get status => _status;
  FirebaseMessaging? get messaging =>
      _status.isReady ? _runtime.messaging : null;

  Future<RuntimeServiceStatus> initialize(MakoloRuntimeConfig config) async {
    if (!config.firebase.enabled) {
      return _status = const RuntimeServiceStatus.disabled();
    }
    if (_status.isReady) return _status;
    _status = const RuntimeServiceStatus(RuntimeServiceState.initializing);
    try {
      await _runtime.initialize();
      _backgroundRegistrar(makoloFirebaseBackgroundMessage);
      return _status = const RuntimeServiceStatus.ready();
    } catch (error) {
      return _status = RuntimeServiceStatus.failed(
        error.runtimeType.toString(),
      );
    }
  }
}
