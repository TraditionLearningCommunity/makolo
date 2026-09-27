import 'package:makolo_mobile/auth/token_store.dart';

class MemoryTokenStore implements TokenStore {
  MemoryTokenStore({this.session, this.deviceId = 'device-test'});

  AuthSession? session;
  final String deviceId;
  final Map<String, DeviceAccount> accounts = {};
  final Map<String, AuthSession> accountSessions = {};

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
    final profileId = value.profileId;
    if (profileId != null && accountSessions.containsKey(profileId)) {
      accountSessions[profileId] = value;
    }
  }

  @override
  Future<List<DeviceAccount>> listAccounts() async {
    final values = accounts.values.toList()
      ..sort((a, b) => b.lastUsedAt.compareTo(a.lastUsedAt));
    return values;
  }

  @override
  Future<void> saveAccount(
    DeviceAccount account, {
    AuthSession? quickAccessSession,
  }) async {
    accounts[account.profileId] = DeviceAccount(
      profileId: account.profileId,
      email: account.email,
      displayName: account.displayName,
      hasQuickAccess: quickAccessSession != null,
      lastUsedAt: account.lastUsedAt,
    );
    if (quickAccessSession == null) {
      accountSessions.remove(account.profileId);
    } else {
      accountSessions[account.profileId] = quickAccessSession;
    }
  }

  @override
  Future<AuthSession?> readAccountSession(String profileId) async {
    return accountSessions[profileId];
  }

  @override
  Future<void> clearAccountSession(String profileId) async {
    accountSessions.remove(profileId);
    final account = accounts[profileId];
    if (account != null) {
      accounts[profileId] = DeviceAccount(
        profileId: account.profileId,
        email: account.email,
        displayName: account.displayName,
        hasQuickAccess: false,
        lastUsedAt: account.lastUsedAt,
      );
    }
  }

  @override
  Future<void> removeAccount(String profileId) async {
    if (session?.profileId == profileId) session = null;
    accounts.remove(profileId);
    accountSessions.remove(profileId);
  }

  @override
  Future<AuthSession> activateAccount(String profileId) async {
    final value = accountSessions[profileId];
    if (value == null) throw StateError('quick access unavailable');
    session = value;
    return value;
  }
}
