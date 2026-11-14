import '../../platform/maps/makolo_map_view.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';

/// Transient presentation memory for Carte. It belongs to the current
/// Discovery repository (and therefore its viewer) and never enters a server
/// projection, offline business store or geographic search request.
class DiscoveryMapVisitState {
  MapViewport? viewport;
  String? selectedCandidateKey;

  /// UX-only hint for an exact departure/stopover/arrival selection.
  /// Never grants a right or replaces the owner's geographic facts.
  DiscoverySpatialAnchor? focusedAnchor;
}

final Expando<Map<String, DiscoveryMapVisitState>> _visits =
    Expando<Map<String, DiscoveryMapVisitState>>('discovery-map-visits');

/// At most twelve explored query contexts are retained in memory per viewer.
DiscoveryMapVisitState discoveryMapVisitState(
  DiscoveryRepository repository,
  String queryFingerprint,
) {
  var visits = _visits[repository];
  if (visits == null) {
    visits = <String, DiscoveryMapVisitState>{};
    _visits[repository] = visits;
  }
  final existing = visits[queryFingerprint];
  if (existing != null) return existing;
  if (visits.length >= 12) {
    visits.remove(visits.keys.first);
  }
  final created = DiscoveryMapVisitState();
  visits[queryFingerprint] = created;
  return created;
}
