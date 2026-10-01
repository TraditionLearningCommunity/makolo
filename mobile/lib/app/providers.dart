import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/token_store.dart';
import '../platform/location/location_capability.dart';
import '../platform/location/location_service.dart';
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
      (_) => const LocationCapability(
        permissions: PermissionHandlerGateway(),
        service: GeolocatorLocationService(),
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
