import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// A display-only AccessCredential, protected outside Drift and media caches.
/// It never authorizes an AccessUse or an offline scanner decision.
class RetainedAccessQr {
  const RetainedAccessQr({
    required this.accessId,
    required this.path,
    required this.payload,
    required this.checkedAt,
    required this.expiresAt,
    this.issuedAt,
  });

  final String accessId;
  final String path;
  final String payload;
  final DateTime checkedAt;
  final DateTime expiresAt;
  final DateTime? issuedAt;

  bool displayableAt(DateTime now) {
    final instant = now.toUtc();
    final checked = checkedAt.toUtc();
    final expiry = expiresAt.toUtc();
    return payload.isNotEmpty &&
        !checked.isAfter(instant) &&
        checked.isBefore(expiry) &&
        instant.isBefore(expiry);
  }
}

abstract interface class AccessCredentialVault {
  Future<RetainedAccessQr?> read(String profileId, String accessId);
  Future<void> save(String profileId, RetainedAccessQr value);
  Future<void> delete(String profileId, String accessId);
  Future<void> clearProfile(String profileId);
}

/// The owner explicitly permits a finite presentation window. The secret is
/// held by platform Keychain/Keystore, not a Profile projection or file.
class SecureAccessCredentialVault implements AccessCredentialVault {
  SecureAccessCredentialVault({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _namespace = 'makolo.access.credential.v1';
  static Future<void> _pending = Future<void>.value();
  final FlutterSecureStorage _storage;

  String _key(String profile, String access) => '$_namespace.$profile.$access';
  String _index(String profile) => '$_namespace.index.$profile';

  Future<void> _serialize(Future<void> Function() operation) {
    final work = _pending.catchError((Object _) {}).then((_) => operation());
    _pending = work.catchError((Object _) {});
    return work;
  }

  Future<Set<String>> _keys(String profile) async {
    final raw = await _storage.read(key: _index(profile));
    if (raw == null) return {};
    try {
      final decoded = jsonDecode(raw);
      return decoded is List ? decoded.whereType<String>().toSet() : {};
    } on FormatException {
      return {};
    }
  }

  Future<void> _writeKeys(String profile, Set<String> keys) => _storage.write(
    key: _index(profile),
    value: jsonEncode(keys.toList()..sort()),
  );

  @override
  Future<RetainedAccessQr?> read(String profileId, String accessId) async {
    await _pending;
    final raw = await _storage.read(key: _key(profileId, accessId));
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map ||
          decoded['v'] != 1 ||
          decoded['profile'] != profileId ||
          decoded['access'] != accessId ||
          decoded['payload'] is! String ||
          decoded['path'] is! String) {
        await delete(profileId, accessId);
        return null;
      }
      final checked = DateTime.tryParse(decoded['checked']?.toString() ?? '');
      final expiry = DateTime.tryParse(decoded['expiry']?.toString() ?? '');
      if (checked == null || expiry == null) {
        await delete(profileId, accessId);
        return null;
      }
      final value = RetainedAccessQr(
        accessId: accessId,
        path: decoded['path'] as String,
        payload: decoded['payload'] as String,
        checkedAt: checked,
        expiresAt: expiry,
        issuedAt: DateTime.tryParse(decoded['issued']?.toString() ?? ''),
      );
      if (!value.displayableAt(DateTime.now())) {
        await delete(profileId, accessId);
        return null;
      }
      return value;
    } on FormatException {
      await delete(profileId, accessId);
      return null;
    }
  }

  @override
  Future<void> save(String profileId, RetainedAccessQr value) {
    if (!value.displayableAt(DateTime.now())) {
      throw const FormatException('Expired Access display permission');
    }
    return _serialize(() async {
      await _storage.write(
        key: _key(profileId, value.accessId),
        value: jsonEncode({
          'v': 1,
          'profile': profileId,
          'access': value.accessId,
          'path': value.path,
          'payload': value.payload,
          'checked': value.checkedAt.toUtc().toIso8601String(),
          'expiry': value.expiresAt.toUtc().toIso8601String(),
          'issued': value.issuedAt?.toUtc().toIso8601String(),
        }),
      );
      final keys = await _keys(profileId);
      keys.add(value.accessId);
      await _writeKeys(profileId, keys);
    });
  }

  @override
  Future<void> delete(String profileId, String accessId) =>
      _serialize(() async {
        await _storage.delete(key: _key(profileId, accessId));
        final keys = await _keys(profileId);
        keys.remove(accessId);
        await _writeKeys(profileId, keys);
      });

  /// Periodic secure-store housekeeping is independent of connectivity.
  /// Only expired, damaged or orphaned display-only credentials are removed.
  Future<void> purgeExpiredProfile(String profileId) => _serialize(() async {
    final keys = await _keys(profileId);
    final keep = <String>{};
    final now = DateTime.now().toUtc();
    for (final accessId in keys) {
      final raw = await _storage.read(key: _key(profileId, accessId));
      var usable = false;
      if (raw != null) {
        try {
          final decoded = jsonDecode(raw);
          if (decoded is Map &&
              decoded['v'] == 1 &&
              decoded['profile'] == profileId &&
              decoded['access'] == accessId &&
              decoded['payload'] is String &&
              (decoded['payload'] as String).isNotEmpty &&
              decoded['path'] is String) {
            final expiry = DateTime.tryParse(
              decoded['expiry']?.toString() ?? '',
            );
            final checked = DateTime.tryParse(
              decoded['checked']?.toString() ?? '',
            );
            usable =
                checked != null &&
                expiry != null &&
                !checked.toUtc().isAfter(now) &&
                checked.toUtc().isBefore(expiry.toUtc()) &&
                now.isBefore(expiry.toUtc());
          }
        } on FormatException {
          // A malformed secure value is not an offline presentation right.
        }
      }
      if (usable) {
        keep.add(accessId);
      } else {
        await _storage.delete(key: _key(profileId, accessId));
      }
    }
    await _writeKeys(profileId, keep);
  });

  @override
  Future<void> clearProfile(String profileId) => _serialize(() async {
    for (final access in await _keys(profileId)) {
      await _storage.delete(key: _key(profileId, access));
    }
    await _storage.delete(key: _index(profileId));
  });
}
