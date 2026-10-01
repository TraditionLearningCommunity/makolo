import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/observability/observability.dart';

void main() {
  test('diagnostic tags discard sensitive and oversized values', () {
    final result = safeDiagnosticTags({
      'feature': 'scanner',
      'token': 'secret-token',
      'qr_payload': 'full-secret-code',
      'credential_id': 'credential',
      'authorization_header': 'Bearer private',
      'password_reset': 'private',
      'client_secret': 'private',
      'accessCredential': 'private',
      'filePath': '/private/path',
      'jwt': 'private',
      'note': 'x' * 121,
      'state': 'offline',
    });

    expect(result, {'feature': 'scanner', 'state': 'offline'});
  });
}
