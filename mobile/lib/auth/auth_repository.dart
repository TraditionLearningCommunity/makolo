import '../network/makolo_api_client.dart';
import 'token_store.dart';

class AuthRepository {
  AuthRepository(this.api, this.tokens);

  final MakoloApiClient api;
  final TokenStore tokens;

  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    var session = await api.login(email: email, password: password);
    try {
      final me = await api.get('api/v1/accounts/auth/me/');
      final profileId = me.jsonObject()['id']?.toString();
      if (profileId == null || profileId.isEmpty) {
        throw const FormatException('auth/me missing id');
      }
      session = AuthSession(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
        profileId: profileId,
      );
      await tokens.writeSession(session);
      return session;
    } on Object {
      await tokens.clearSession();
      rethrow;
    }
  }

  Future<void> logout() async {
    final session = await tokens.readSession();
    if (session == null) return;
    try {
      await api.post(
        'api/v1/accounts/auth/logout/',
        body: {'refresh': session.refreshToken},
      );
    } on Object {
      // Local credentials are still removed. The server-side refresh may
      // already be expired/revoked or the device may be offline.
    } finally {
      await tokens.clearSession();
    }
  }
}
