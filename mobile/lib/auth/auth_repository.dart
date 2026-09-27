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

  Future<void> register({
    required String email,
    required String username,
    required String password,
    required String passwordConfirm,
    String? firstName,
    String? lastName,
    String? phone,
  }) async {
    await api.register(
      email: email,
      username: username,
      password: password,
      passwordConfirm: passwordConfirm,
      firstName: firstName,
      lastName: lastName,
      phone: phone,
    );
  }

  Future<void> forgotPassword({required String email}) async {
    await api.forgotPassword(email: email);
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
    required String newPasswordConfirm,
  }) async {
    await api.changePassword(
      currentPassword: currentPassword,
      newPassword: newPassword,
      newPasswordConfirm: newPasswordConfirm,
    );
    await tokens.clearSession();
  }

  Future<void> logout() async {
    final session = await tokens.readSession();
    if (session == null) return;

    // Remove local credentials before any network dependency. The Profile DB,
    // drafts and outbox live outside TokenStore and are intentionally preserved.
    await tokens.clearSession();
    try {
      await api.logoutSession(session);
    } on Object {
      // Best-effort server blacklist. Local logout remains effective when the
      // server is unreachable or the refresh has already expired/revoked.
    }
  }
}
