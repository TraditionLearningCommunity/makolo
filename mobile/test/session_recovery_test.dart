import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/session_recovery.dart';

void main() {
  test('session recovery restores the last useful route once', () {
    final recovery = SessionRecoveryController();

    recovery.rememberLocation('/ongoing');
    recovery.markSessionExpired();

    expect(recovery.awaitingAuthentication, isTrue);
    expect(recovery.initialLocation(), '/ongoing');
    expect(recovery.awaitingAuthentication, isFalse);
    expect(recovery.initialLocation(), '/now');
  });

  test('session recovery ignores empty/root-only locations', () {
    final recovery = SessionRecoveryController();

    recovery.rememberLocation('/');
    recovery.markSessionExpired();

    expect(recovery.initialLocation(), '/now');
  });
}
