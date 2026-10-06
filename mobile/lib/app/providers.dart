import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/token_store.dart';
import '../platform/location/location_capability.dart';
import '../platform/location/location_service.dart';
import '../platform/notifications/push_endpoint_registrar.dart';
import '../platform/notifications/push_token_source.dart';
import '../platform/permissions/permission_gateway.dart';
import 'environment.dart';
import 'runtime/app_runtime.dart';
import 'runtime/runtime_builder.dart';
import 'session_recovery.dart';

export 'runtime/app_runtime.dart';

final tokenStoreProvider = Provider<TokenStore>(
  (ref) => FlutterSecureTokenStore(),
);

final sessionRecoveryProvider = Provider<SessionRecoveryController>(
  (ref) => SessionRecoveryController(),
);

final runtimeConfigProvider = Provider<MakoloRuntimeConfig>(
  (ref) => MakoloRuntimeConfig.fromEnvironment(),
);

final locationCapabilityFactoryProvider = Provider<LocationCapabilityFactory>(
  (ref) =>
      (config) => LocationCapability(
        permissions: const PermissionHandlerGateway(),
        service: const GeolocatorLocationService(),
        backgroundCapabilityEnabled:
            config.location.backgroundCapabilityEnabled,
      ),
);

final appRuntimeProvider = FutureProvider<AppRuntime>((ref) async {
  final runtime = await buildAppRuntime(
    tokens: ref.watch(tokenStoreProvider),
    recovery: ref.watch(sessionRecoveryProvider),
    config: ref.watch(runtimeConfigProvider),
    locationFactory: ref.watch(locationCapabilityFactoryProvider),
  );
  ref.onDispose(() => unawaited(runtime.close()));
  return runtime;
});

final pushEndpointRegistrationProvider = FutureProvider.autoDispose<void>(
  (ref) async {
    final runtime = await ref.watch(appRuntimeProvider.future);
    final config = runtime.config;
    final api = runtime.api;
    if (!runtime.isAuthenticated ||
        config == null ||
        !config.firebase.enabled ||
        api == null) {
      return;
    }

    final registrar = PushEndpointRegistrar(
      api: api,
      tokens: runtime.tokens,
      source: FirebasePushTokenSource(FirebaseMessaging.instance),
    );
    ref.onDispose(registrar.dispose);
    await registrar.start();
  },
);
