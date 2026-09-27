import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/sync/projection_contract.dart';

void main() {
  test('accepts additive v1 projection fields', () {
    final envelope = ProjectionEnvelope.parse({
      'meta': {
        'projection': 'personal.now',
        'schema_version': 1,
        'generated_at': '2026-09-26T10:00:00Z',
        'scope': 'personal',
        'future_additive_field': true,
      },
      'data': {
        'items': <Object>[],
        'future_section': {'safe': true},
      },
    });

    expect(envelope.projection, 'personal.now');
    expect(envelope.schemaVersion, 1);
    expect(envelope.data['items'], isEmpty);
  });

  test('rejects an incompatible schema version', () {
    expect(
      () => ProjectionEnvelope.parse({
        'meta': {'projection': 'personal.now', 'schema_version': 2},
        'data': <String, dynamic>{},
      }),
      throwsFormatException,
    );
  });
}
