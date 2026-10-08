import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    this.profileId,
  });

  final String accessToken;
  final String refreshToken;
  final String? profileId;

  AuthSession copyWith({
    String? accessToken,
    String? refreshToken,
    String? profileId,
  }) {
    return AuthSession(
      accessToken: accessToken ?? this.accessToken,
      refreshToken: refreshToken ?? this.refreshToken,
      profileId: profileId ?? this.profileId,
    );
  }

  Map<String, dynamic> toJson() => {
    'access': accessToken,
    'refresh': refreshToken,
    'profile_id': profileId,
  };

  static AuthSession fromJson(Map<String, dynamic> json) => AuthSession(
    accessToken: json['access'] as String,
    refreshToken: json['refresh'] as String,
    profileId: json['profile_id'] as String?,
  );
}

class DeviceAccount {
  const DeviceAccount({
    required this.profileId,
    this.username = '',
    this.email,
    required this.displayName,
    required this.hasQuickAccess,
    required this.lastUsedAt,
  });

  final String profileId;
  final String username;
  final String? email;
  final String displayName;
  final bool hasQuickAccess;
  final DateTime lastUsedAt;

  String get publicIdentifier {
    final normalized = username.trim().replaceFirst(RegExp(r'^@'), '');
    if (normalized.isNotEmpty) return '@$normalized';
    final mail = email?.trim();
    return mail == null || mail.isEmpty ? 'Compte Makolo' : mail;
  }

  String get loginIdentifier {
    final normalized = username.trim().replaceFirst(RegExp(r'^@'), '');
    if (normalized.isNotEmpty) return normalized;
    return email?.trim() ?? '';
  }

  String get avatarLetter {
    final source = username.trim().isNotEmpty
        ? username
        : (displayName.trim().isNotEmpty ? displayName : email ?? 'M');
    return source.trim().replaceFirst(RegExp(r'^@'), '').substring(0, 1).toUpperCase();
  }
}

abstract interface class TokenStore {
  Future<AuthSession?> readSession();
  Future<void> writeSession(AuthSession session);
  Future<void> clearSession();
  Future<String> deviceInstanceId();

  Future<List<DeviceAccount>> listAccounts();
  Future<void> saveAccount(
    DeviceAccount account, {
    AuthSession? quickAccessSession,
  });
  Future<AuthSession?> readAccountSession(String profileId);
  Future<void> clearAccountSession(String profileId);
  Future<void> removeAccount(String profileId);
  Future<AuthSession> activateAccount(String profileId);
}

class FlutterSecureTokenStore implements TokenStore {
  FlutterSecureTokenStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _sessionKey = 'makolo.active_session.v1';
  static const _deviceKey = 'makolo.device_instance_id.v1';
  static const _accountsKey = 'makolo.device_accounts.v1';

  final FlutterSecureStorage _storage;

  @override
  Future<AuthSession?> readSession() async {
    final raw = await _storage.read(key: _sessionKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      return AuthSession.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } on Object {
      await _storage.delete(key: _sessionKey);
      return null;
    }
  }

  @override
  Future<void> writeSession(AuthSession session) async {
    await _storage.write(key: _sessionKey, value: jsonEncode(session.toJson()));

    final profileId = session.profileId;
    if (profileId == null || profileId.isEmpty) return;
    final accounts = await _readAccountRecords();
    final record = accounts[profileId];
    if (record == null || record['session'] == null) return;
    record['session'] = session.toJson();
    record['last_used_at'] = DateTime.now().toUtc().toIso8601String();
    await _writeAccountRecords(accounts);
  }

  @override
  Future<void> clearSession() => _storage.delete(key: _sessionKey);

  @override
  Future<String> deviceInstanceId() async {
    final existing = await _storage.read(key: _deviceKey);
    if (existing != null && existing.isNotEmpty) return existing;
    final random = Random.secure();
    final value = List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    await _storage.write(key: _deviceKey, value: value);
    return value;
  }

  @override
  Future<List<DeviceAccount>> listAccounts() async {
    final records = await _readAccountRecords();
    final accounts = <DeviceAccount>[];
    for (final entry in records.entries) {
      final value = entry.value;
      final rawUsername = value['username'];
      final username = rawUsername is String ? rawUsername.trim() : '';
      final rawEmail = value['email'];
      final email = rawEmail is String && rawEmail.trim().isNotEmpty
          ? rawEmail.trim()
          : null;
      final displayName = value['display_name'];
      final lastUsedRaw = value['last_used_at'];
      if (username.isEmpty && email == null) continue;
      accounts.add(
        DeviceAccount(
          profileId: entry.key,
          username: username,
          email: email,
          displayName: displayName is String && displayName.trim().isNotEmpty
              ? displayName
              : (username.isNotEmpty ? '@$username' : email!),
          hasQuickAccess: value['session'] is Map,
          lastUsedAt:
              DateTime.tryParse(lastUsedRaw is String ? lastUsedRaw : '') ??
              DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
        ),
      );
    }
    accounts.sort((a, b) => b.lastUsedAt.compareTo(a.lastUsedAt));
    return accounts;
  }

  @override
  Future<void> saveAccount(
    DeviceAccount account, {
    AuthSession? quickAccessSession,
  }) async {
    final accounts = await _readAccountRecords();
    accounts[account.profileId] = <String, dynamic>{
      'username': account.username,
      'email': account.email,
      'display_name': account.displayName,
      'last_used_at': account.lastUsedAt.toUtc().toIso8601String(),
      'session': quickAccessSession?.toJson(),
    };
    await _writeAccountRecords(accounts);
  }

  @override
  Future<AuthSession?> readAccountSession(String profileId) async {
    final record = (await _readAccountRecords())[profileId];
    final raw = record?['session'];
    if (raw is! Map) return null;
    try {
      return AuthSession.fromJson(Map<String, dynamic>.from(raw));
    } on Object {
      await clearAccountSession(profileId);
      return null;
    }
  }

  @override
  Future<void> clearAccountSession(String profileId) async {
    final accounts = await _readAccountRecords();
    final record = accounts[profileId];
    if (record == null) return;
    record['session'] = null;
    await _writeAccountRecords(accounts);
  }

  @override
  Future<void> removeAccount(String profileId) async {
    final active = await readSession();
    if (active?.profileId == profileId) {
      await clearSession();
    }
    final accounts = await _readAccountRecords();
    if (accounts.remove(profileId) != null) {
      await _writeAccountRecords(accounts);
    }
  }

  @override
  Future<AuthSession> activateAccount(String profileId) async {
    final session = await readAccountSession(profileId);
    if (session == null) {
      throw StateError('quick access unavailable');
    }
    await writeSession(session);
    return session;
  }

  Future<Map<String, Map<String, dynamic>>> _readAccountRecords() async {
    final raw = await _storage.read(key: _accountsKey);
    if (raw == null || raw.isEmpty) return {};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return {};
      final result = <String, Map<String, dynamic>>{};
      for (final entry in decoded.entries) {
        if (entry.key is String && entry.value is Map) {
          result[entry.key as String] = Map<String, dynamic>.from(
            entry.value as Map,
          );
        }
      }
      return result;
    } on Object {
      await _storage.delete(key: _accountsKey);
      return {};
    }
  }

  Future<void> _writeAccountRecords(
    Map<String, Map<String, dynamic>> accounts,
  ) {
    return _storage.write(key: _accountsKey, value: jsonEncode(accounts));
  }
}
