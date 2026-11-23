import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Best-effort UI preferences, keyed by Profile/Space by their callers.
/// Sensitive credentials belong in a dedicated credential vault instead.
class SecureStringPreferences {
  const SecureStringPreferences();

  static const FlutterSecureStorage _storage = FlutterSecureStorage();

  Future<String?> read({required String key}) => _storage.read(key: key);

  Future<void> write({required String key, required String value}) =>
      _storage.write(key: key, value: value);
}
