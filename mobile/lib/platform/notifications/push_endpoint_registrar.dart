import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../auth/token_store.dart';
import '../../network/makolo_api_client.dart';
import 'push_token_source.dart';

class PushEndpointRegistrar {
  PushEndpointRegistrar({
    required this.api,
    required this.tokens,
    required this.source,
  });

  final MakoloApiClient api;
  final TokenStore tokens;
  final PushTokenSource source;

  static const _deviceChannel = MethodChannel('makolo/device');
  StreamSubscription<String>? _subscription;

  Future<String> _readDeviceName() async {
    if (!Platform.isAndroid) return '';
    try {
      return (await _deviceChannel.invokeMethod<String>('name'))?.trim() ?? '';
    } on Object {
      // Missing platform support must not prevent registration.
      return '';
    }
  }

  bool _disposed = false;

  Future<void> _register(String token, {bool reactivate = false}) async {
    final platform = _platform;
    if (_disposed || platform == null || token.trim().isEmpty) return;
    final installationId = await tokens.deviceInstanceId();
    final info = await PackageInfo.fromPlatform();
    final deviceName = await _readDeviceName();
    final appVersion = info.buildNumber.isEmpty
        ? info.version
        : '${info.version}+${info.buildNumber}';
    await api.post(
      'api/v1/notifications/push/endpoints/',
      body: {
        'provider': 'fcm',
        'platform': platform,
        'installation_id': installationId,
        'token': token.trim(),
        'app_version': appVersion,
        'device_name': deviceName,
        'reactivate': reactivate,
      },
    );
  }

  /// Only an explicit user gesture may restore a revoked installation.
  Future<void> reactivateCurrent() async {
    final token = await source.currentToken();
    if (token == null || token.trim().isEmpty) {
      throw StateError('Aucun token push disponible sur cet appareil.');
    }
    await _register(token, reactivate: true);
  }

  Future<void> _registerAutomatically(String token) async {
    try {
      await _register(token);
    } on Object {
      // Best effort only: a revoked endpoint or an installation belonging to
      // a previous Profile must not crash app startup or stop token listening.
      // Never retry with reactivate=true without a deliberate user gesture.
    }
  }

  Future<void> start() async {
    if (_platform == null) return;

    String? current;
    try {
      current = await source.currentToken();
    } on Object {
      // Continue to listen for later token refresh even if startup failed.
    }
    if (current != null && current.trim().isNotEmpty) {
      await _registerAutomatically(current);
    }

    if (_disposed) return;
    _subscription = source.tokenChanges.listen(
      (token) => unawaited(_registerAutomatically(token)),
      onError: (_) {
        // Best effort; user opt-in in Connexions remains available.
      },
    );
  }

  Future<void> revoke() async {
    final installationId = await tokens.deviceInstanceId();
    await api.delete(
      'api/v1/notifications/push/endpoints/',
      body: {'provider': 'fcm', 'installation_id': installationId},
    );
  }

  void dispose() {
    _disposed = true;
    unawaited(_subscription?.cancel());
  }

  String? get _platform {
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'ios';
    return null;
  }
}
