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

  Future<void> start() async {
    final platform = _platform;
    if (platform == null) return;

    final installationId = await tokens.deviceInstanceId();
    final info = await PackageInfo.fromPlatform();
    final appVersion = info.buildNumber.isEmpty
        ? info.version
        : '${info.version}+${info.buildNumber}';

    Future<void> register(String token) async {
      if (_disposed || token.trim().isEmpty) return;
      await api.post(
        'api/v1/notifications/push/endpoints/',
        body: {
          'provider': 'fcm',
          'platform': platform,
          'installation_id': installationId,
          'token': token.trim(),
          'app_version': appVersion,
        },
      );
    }

    final current = await source.currentToken();
    if (current != null && current.trim().isNotEmpty) {
      await register(current);
    }

    _subscription = source.tokenChanges.listen(
      (token) => unawaited(register(token)),
      onError: (_) {
        // Push registration is best-effort. Canonical data and local-first
        // execution remain usable when FCM is temporarily unavailable.
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
