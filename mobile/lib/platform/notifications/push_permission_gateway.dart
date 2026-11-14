import 'package:firebase_messaging/firebase_messaging.dart';

/// Device-level permission; the server endpoint registrar separately
/// confirms that this Profile's token is registered.
abstract final class PushPermissionGateway {
  static Future<bool> request() async {
    final decision = await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: false,
      sound: true,
    );
    return decision.authorizationStatus != AuthorizationStatus.denied;
  }
}
