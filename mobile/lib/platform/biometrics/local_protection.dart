import 'package:local_auth/local_auth.dart';

abstract interface class LocalProtection {
  Future<bool> isAvailable();

  Future<bool> authenticate({
    required String reason,
    bool biometricOnly = false,
  });

  Future<void> cancel();
}

class LocalAuthProtection implements LocalProtection {
  LocalAuthProtection({LocalAuthentication? authentication})
    : _authentication = authentication ?? LocalAuthentication();

  final LocalAuthentication _authentication;

  @override
  Future<bool> isAvailable() => _authentication.isDeviceSupported();

  @override
  Future<bool> authenticate({
    required String reason,
    bool biometricOnly = false,
  }) {
    return _authentication.authenticate(
      localizedReason: reason,
      biometricOnly: biometricOnly,
      persistAcrossBackgrounding: true,
      sensitiveTransaction: true,
    );
  }

  @override
  Future<void> cancel() async {
    await _authentication.stopAuthentication();
  }
}
