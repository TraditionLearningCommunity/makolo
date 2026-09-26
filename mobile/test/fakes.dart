import 'package:makolo_mobile/auth/token_store.dart';

class MemoryTokenStore implements TokenStore {
  MemoryTokenStore({this.session, this.deviceId = 'device-test'});

  AuthSession? session;
  final String deviceId;

  @override
  Future<void> clearSession() async {
    session = null;
  }

  @override
  Future<String> deviceInstanceId() async => deviceId;

  @override
  Future<AuthSession?> readSession() async => session;

  @override
  Future<void> writeSession(AuthSession value) async {
    session = value;
  }
}
