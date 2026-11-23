import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/services/service_start_screen.dart';
import 'package:makolo_mobile/network/api_error.dart';

void main() {
  MakoloApiError status(int code) => MakoloApiError(
    statusCode: code,
    code: 'http_$code',
    message: 'Réponse autoritative du serveur',
  );

  test('a validation rejection allows corrected data, not blind replay', () {
    expect(
      classifyServiceStartFailure(status(400)),
      ServiceStartFailureKind.rejected,
    );
    expect(
      classifyServiceStartFailure(status(422)),
      ServiceStartFailureKind.rejected,
    );
  });

  test('an idempotence conflict requires a deliberate new intention', () {
    expect(
      classifyServiceStartFailure(status(409)),
      ServiceStartFailureKind.conflict,
    );
  });

  test('owner access loss cannot be retried as if network were down', () {
    for (final code in [401, 403, 404]) {
      expect(
        classifyServiceStartFailure(status(code)),
        ServiceStartFailureKind.unavailable,
      );
    }
  });

  test('transport uncertainty preserves the same operation for replay', () {
    expect(
      classifyServiceStartFailure(
        const MakoloTransportError('timeout', 'Délai dépassé'),
      ),
      ServiceStartFailureKind.retryable,
    );
    expect(
      classifyServiceStartFailure(status(503)),
      ServiceStartFailureKind.retryable,
    );
    expect(
      classifyServiceStartFailure(const FormatException('Bad response')),
      ServiceStartFailureKind.retryable,
    );
  });
}
