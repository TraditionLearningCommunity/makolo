import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/navigation/deep_link_resolver.dart';
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

  test('server kinds without a current mobile route stay unresolved', () {
    final destination = codec.fromNavigation({
      'schema_version': 1,
      'resource': {'kind': 'personal_asset', 'id': 'asset-1'},
    });

    expect(destination, isNotNull);
    expect(const DeepLinkResolver().resolve(destination!), isNull);
  });
}
