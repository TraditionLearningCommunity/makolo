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

abstract interface class TokenStore {
  Future<AuthSession?> readSession();
  Future<void> writeSession(AuthSession session);
  Future<void> clearSession();
  Future<String> deviceInstanceId();
}

class FlutterSecureTokenStore implements TokenStore {
  FlutterSecureTokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _sessionKey = 'makolo.active_session.v1';
  static const _deviceKey = 'makolo.device_instance_id.v1';

  final FlutterSecureStorage _storage;

  @override
  Future<AuthSession?> readSession() async {
    final raw = await _storage.read(key: _sessionKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      return AuthSession.fromJson(
        jsonDecode(raw) as Map<String, dynamic>,
      );
    } on Object {
      await _storage.delete(key: _sessionKey);
      return null;
    }
  }

  @override
  Future<void> writeSession(AuthSession session) {
    // Access + rotated refresh are replaced as one secure-storage value.
    return _storage.write(
      key: _sessionKey,
      value: jsonEncode(session.toJson()),
    );
  }

  @override
  Future<void> clearSession() => _storage.delete(key: _sessionKey);

  @override
  Future<String> deviceInstanceId() async {
    final existing = await _storage.read(key: _deviceKey);
    if (existing != null && existing.isNotEmpty) return existing;
    final random = Random.secure();
    final value = List<int>.generate(16, (_) => random.nextInt(256))
        .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
        .join();
    await _storage.write(key: _deviceKey, value: value);
    return value;
  }
}
