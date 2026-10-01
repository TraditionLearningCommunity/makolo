import 'package:firebase_messaging/firebase_messaging.dart';

abstract interface class PushTokenSource {
  Future<String?> currentToken();
  Stream<String> get tokenChanges;
}

class FirebasePushTokenSource implements PushTokenSource {
  FirebasePushTokenSource(this.messaging);

  final FirebaseMessaging messaging;

  @override
  Future<String?> currentToken() => messaging.getToken();

  @override
  Stream<String> get tokenChanges => messaging.onTokenRefresh;
}
