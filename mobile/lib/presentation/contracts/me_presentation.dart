import '../../design/surface_states.dart';
import '../../navigation/destination.dart';

class MeTerritoryPresentation {
  const MeTerritoryPresentation({
    required this.key,
    required this.label,
    required this.state,
    this.summary,
    this.items = const [],
    this.depth,
  });

  final String key;
  final String label;
  final String? summary;
  final List<StructuredDestination> items;
  final StructuredDestination? depth;
  final MakoloSurfacePresentation state;
}

class MePresentation {
  const MePresentation({
    required this.identityLabel,
    required this.territories,
  });

  final String identityLabel;
  final List<MeTerritoryPresentation> territories;
}
