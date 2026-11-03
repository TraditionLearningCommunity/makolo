import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/interoperability/space_connections_screen.dart';
import 'package:makolo_mobile/features/interoperability/interoperability_presentation.dart';
import 'package:makolo_mobile/repositories/interoperability_repository.dart';

InteroperabilityConnectionProjection connection({
  String health = 'unknown',
  bool enabled = true,
  bool usable = true,
  List<String> capabilities = const ['web_research'],
}) {
  return InteroperabilityConnectionProjection(
    id: 'space-provider',
    displayName: 'Recherche du Space',
    owner: 'intelligence',
    scope: 'space',
    providerProtocol: 'tavily_search',
    available: true,
    connected: true,
    usable: usable,
    manageable: true,
    enabled: enabled,
    status: enabled ? 'connected' : 'disabled',
    health: health,
    capabilities: capabilities,
  );
}

void main() {
  test(
    'Profile and Space share the same server-owned presentation vocabulary',
    () {
      for (final health in ['healthy', 'unknown', 'degraded', 'unavailable']) {
        final row = connection(health: health);
        expect(spaceConnectionStatus(row), connectionStatusLabel(row));
      }
      expect(
        connectionExperienceMessage(connection()),
        'La disponibilité doit être vérifiée.',
      );
      expect(
        connectionExperienceMessage(connection(health: 'healthy')),
        'Ce service est prêt à être utilisé.',
      );
      expect(
        connectionExperienceMessage(connection(enabled: false)),
        'Cette connexion est désactivée.',
      );
    },
  );

  test('unverified new provider is never shown as confirmed available', () {
    expect(spaceConnectionStatus(connection()), 'Connecté · état à vérifier');
    expect(
      spaceConnectionStatus(connection(health: 'healthy')),
      'Connecté et disponible',
    );
    expect(
      spaceConnectionStatus(connection(health: 'degraded')),
      'Connecté · disponibilité réduite',
    );
    expect(
      spaceConnectionStatus(connection(health: 'unavailable')),
      'Momentanément indisponible',
    );
    expect(spaceConnectionStatus(connection(enabled: false)), 'Désactivé');
    expect(
      spaceConnectionStatus(connection(health: 'healthy', capabilities: [])),
      'Connecté · aucun usage disponible',
    );
    expect(
      spaceConnectionStatus(connection(health: 'healthy', usable: false)),
      'Connecté',
    );
  });
}
