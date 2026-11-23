import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/repositories/interoperability_repository.dart';

void main() {
  test('Z16 profile parses owner handoffs separately from connections', () {
    final stored = StoredProjection(
      kind: ProfileInteroperabilityRepository.projectionKind,
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 2),
      payload: const {
        'schema_version': 'z16.v1',
        'context': 'profile',
        'providers': [],
        'connections': [],
        'actions': [],
        'extensions': [],
        'domain_integrations': [
          {
            'code': 'notifications.push',
            'owner': 'notifications',
            'kind': 'device_registration',
            'display_name': 'Notifications sur mes appareils',
            'status': 'registered',
            'available': false,
            'connected': true,
            'active_count': 1,
            'description': 'Appareils inscrits.',
          },
          {
            'code': 'payments.sandbox',
            'owner': 'payments',
            'kind': 'processing_capability',
            'display_name': 'Paiement de démonstration',
            'status': 'sandbox_only',
            'available': true,
            'connected': false,
            'description': 'Simulation uniquement.',
          },
        ],
      },
    );
    final projection = ProfileInteroperabilityProjection.fromStored(stored);
    expect(projection.isEmpty, false);
    expect(projection.connections, isEmpty);
    expect(projection.domainIntegrations, hasLength(2));
    expect(projection.domainIntegrations.first.activeCount, 1);
    expect(projection.domainIntegrations.last.connected, false);
    expect(projection.domainIntegrations.last.status, 'sandbox_only');
  });

  test('legacy Z16 projection remains valid without the optional C6 field', () {
    final stored = StoredProjection(
      kind: ProfileInteroperabilityRepository.projectionKind,
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 2),
      payload: const {
        'schema_version': 'z16.v1',
        'context': 'profile',
        'providers': [],
        'connections': [],
        'actions': [],
        'extensions': [],
      },
    );
    final projection = ProfileInteroperabilityProjection.fromStored(stored);
    expect(projection.isEmpty, true);
    expect(projection.domainIntegrations, isEmpty);
  });
}
