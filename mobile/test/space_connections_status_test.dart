import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/interoperability/space_connections_screen.dart';
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
  test('unverified new provider is never shown as confirmed available', () {
    expect(
      spaceConnectionStatus(connection()),
      'Reliée · disponibilité à vérifier',
    );
    expect(
      spaceConnectionStatus(connection(health: 'healthy')),
      'Connectée et disponible',
    );
    expect(
      spaceConnectionStatus(connection(health: 'degraded')),
      'Connectée · disponibilité réduite',
    );
    expect(
      spaceConnectionStatus(connection(health: 'unavailable')),
      'Momentanément indisponible',
    );
    expect(spaceConnectionStatus(connection(enabled: false)), 'Désactivée');
    expect(
      spaceConnectionStatus(connection(health: 'healthy', capabilities: [])),
      'Reliée · aucune capacité active',
    );
    expect(
      spaceConnectionStatus(connection(health: 'healthy', usable: false)),
      'Reliée · non utilisable',
    );
  });
}
