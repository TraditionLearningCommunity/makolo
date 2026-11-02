import 'dart:async';
import 'dart:io';

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

  StreamSubscription<String>? _subscription;
  bool _disposed = false;

  Future<void> _register(String token, {bool reactivate = false}) async {
    final platform = _platform;
    if (_disposed || platform == null || token.trim().isEmpty) return;
    final installationId = await tokens.deviceInstanceId();
    final info = await PackageInfo.fromPlatform();
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

  Future<void> start() async {
    if (_platform == null) return;

    final current = await source.currentToken();
    if (current != null && current.trim().isNotEmpty) {
      await _register(current);
    }

    _subscription = source.tokenChanges.listen(
      (token) => unawaited(_register(token)),
      onError: (_) {
        // Best effort; the owner will not undo a user-revoked registration.
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
