import '../../design/surface_states.dart';
import '../../navigation/destination.dart';

enum NowPresentationEmphasis { primary, secondary }

class NowSituationPresentation {
  const NowSituationPresentation({
    required this.reference,
    required this.humanContext,
    required this.meaning,
    required this.emphasis,
    required this.ownerDestination,
    this.whyNow,
    this.responseLabel,
    this.responseCapability,
    this.metadata = const [],
    this.mediaRef,
    this.freshness = MakoloFreshnessCue.unknown,
  });

  final StructuredDestination reference;
  final String humanContext;
  final String meaning;
  final String? whyNow;
  final NowPresentationEmphasis emphasis;
  final String? responseLabel;
  final String? responseCapability;
  final List<String> metadata;
  final String? mediaRef;
  final MakoloFreshnessCue freshness;
  final StructuredDestination ownerDestination;
}
