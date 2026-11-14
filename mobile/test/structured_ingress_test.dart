import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/navigation/deep_link_resolver.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/navigation/incoming_intent.dart';
import 'package:makolo_mobile/navigation/structured_destination_codec.dart';
import 'package:makolo_mobile/platform/scanner/code_scanner.dart';

void main() {
  const codec = StructuredDestinationCodec();

  test(
    'canonical notification navigation v1 becomes a structured destination',
    () {
      final destination = codec.fromNavigation({
        'schema_version': 1,
        'target': 'journey',
        'resource': {'kind': 'journey', 'id': 'j-1'},
        'links': {'api': '/api/v1/me/journeys/j-1/'},
      });

      expect(destination?.kind, 'journey');
      expect(destination?.id, 'j-1');
      expect(destination?.link, '/api/v1/me/journeys/j-1/');
      expect(const DeepLinkResolver().resolve(destination!), '/journeys/j-1');
    },
  );

  test('unknown schema and arbitrary QR text do not become navigation', () {
    expect(
      codec.fromNavigation({
        'schema_version': 2,
        'resource': {'kind': 'journey', 'id': 'j-1'},
      }),
      isNull,
    );
    expect(
      const ScannedCodeIngress().navigationIntent(
        const ScannedCode(value: 'access-secret-or-arbitrary-text'),
      ),
      isNull,
    );
  });

  test('QR navigation still goes through auth recovery', () {
    final intent = const ScannedCodeIngress().navigationIntent(
      const ScannedCode(
        value: '{"schema_version":1,"resource":{"kind":"access","id":"a-1"}}',
      ),
    );
    final recovery = SessionRecoveryController();
    final resolution = const IncomingIntentResolver().resolve(
      intent: intent!,
      authenticated: false,
      recovery: recovery,
    );

    expect(resolution?.route, '/login');
    expect(resolution?.requiresAuthentication, isTrue);
    expect(recovery.initialLocation(), '/accesses/a-1');
  });

  test('personal resource kinds resolve to their canonical owner depths', () {
    const resolver = DeepLinkResolver();
    for (final row in const [
      ('personal_asset', 'asset-1', '/me/resources/documents/asset-1'),
      ('resource', 'asset-2', '/me/resources/documents/asset-2'),
      ('proof', 'proof-1', '/me/resources/proofs/proof-1'),
      ('credential', 'credential-1', '/me/resources/titles/credential-1'),
    ]) {
      final destination = codec.fromNavigation({
        'schema_version': 1,
        'resource': {'kind': row.$1, 'id': row.$2},
      });
      expect(destination, isNotNull);
      expect(resolver.resolve(destination!), row.$3);
    }
  });

  test(
    'personal resource ingress still goes through authentication recovery',
    () {
      const destination = StructuredDestination(kind: 'proof', id: 'proof-1');
      final recovery = SessionRecoveryController();
      final resolution = const IncomingIntentResolver().resolve(
        intent: const IncomingIntent(
          source: IncomingIntentSource.notification,
          destination: destination,
        ),
        authenticated: false,
        recovery: recovery,
      );

      expect(resolution?.route, '/login');
      expect(resolution?.requiresAuthentication, isTrue);
      expect(recovery.initialLocation(), '/me/resources/proofs/proof-1');
    },
  );
}
