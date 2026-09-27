import '../network/makolo_api_client.dart';
import 'token_store.dart';

class AuthRepository {
  AuthRepository(this.api, this.tokens);

  final MakoloApiClient api;
  final TokenStore tokens;

  Future<AuthSession> login({
    required String email,
    required String password,
    bool rememberOnDevice = false,
  }) async {
    var session = await api.login(email: email, password: password);
    try {
      final me = await api.get('api/v1/accounts/auth/me/');
      final payload = me.jsonObject();
      final profileId = payload['id']?.toString();
      if (profileId == null || profileId.isEmpty) {
        throw const FormatException('auth/me missing id');
      }

      session = AuthSession(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
        profileId: profileId,
      );
      await tokens.writeSession(session);

      final canonicalEmail = payload['email'] is String
          ? (payload['email'] as String).trim()
          : email.trim();
      final fullName = payload['full_name'] is String
          ? (payload['full_name'] as String).trim()
          : '';
      final username = payload['username'] is String
          ? (payload['username'] as String).trim()
          : '';
      final displayName = fullName.isNotEmpty
          ? fullName
          : (username.isNotEmpty ? username : canonicalEmail);

      await tokens.saveAccount(
        DeviceAccount(
          profileId: profileId,
          email: canonicalEmail,
          displayName: displayName,
          hasQuickAccess: rememberOnDevice,
          lastUsedAt: DateTime.now().toUtc(),
        ),
        quickAccessSession: rememberOnDevice ? session : null,
      );
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

  Future<AuthSession> registerAndLogin({
    required String email,
    required String username,
    required String password,
    required String passwordConfirm,
    String? firstName,
    String? lastName,
    String? phone,
    bool rememberOnDevice = false,
  }) async {
    await register(
      email: email,
      username: username,
      password: password,
      passwordConfirm: passwordConfirm,
      firstName: firstName,
      lastName: lastName,
      phone: phone,
    );
    return login(
      email: email,
      password: password,
      rememberOnDevice: rememberOnDevice,
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
    final profileId = (await tokens.readSession())?.profileId;
    await tokens.clearSession();
    if (profileId != null) {
      await tokens.clearAccountSession(profileId);
    }
  }

  Future<void> logout({void Function()? onLocalSessionEnded}) async {
    final session = await tokens.readSession();
    if (session == null) {
      onLocalSessionEnded?.call();
      return;
    }

    await tokens.clearSession();
    final serverLogout = api.logoutSession(session);
    onLocalSessionEnded?.call();
    try {
      await serverLogout;
    } on Object {
      // Best-effort server blacklist. Local logout remains effective when the
      // server is unreachable or the refresh has already expired/revoked.
    }
  }
}
