import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/navigation/incoming_intent.dart';

void main() {
  const resolver = IncomingIntentResolver();

  test('authenticated ingress resolves to canonical route', () {
    final recovery = SessionRecoveryController();
    final result = resolver.resolve(
      intent: const IncomingIntent(
        source: IncomingIntentSource.qr,
        destination: StructuredDestination(kind: 'Journey', id: 'j-1'),
      ),
      authenticated: true,
      recovery: recovery,
    );

    expect(result?.route, '/journeys/j-1');
    expect(result?.requiresAuthentication, isFalse);
  });

  test('protected ingress preserves route across authentication', () {
    final recovery = SessionRecoveryController();
    final result = resolver.resolve(
      intent: const IncomingIntent(
        source: IncomingIntentSource.push,
        destination: StructuredDestination(kind: 'Access', id: 'a-1'),
      ),
      authenticated: false,
      recovery: recovery,
    );

    expect(result?.route, '/login');
    expect(recovery.entryReason, EntryReason.protectedIntent);
    expect(recovery.initialLocation(), '/accesses/a-1');
  });
}
