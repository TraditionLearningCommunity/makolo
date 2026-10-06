import '../../design/surface_states.dart';
import '../../navigation/destination.dart';

enum NowPresentationEmphasis { primary, secondary }

enum NowContinuationState { more, end, unknown }

class NowContinuationPresentation {
  const NowContinuationPresentation({required this.state, this.token});

  final NowContinuationState state;
  final String? token;
}

class NowSituationPresentation {
  const NowSituationPresentation({
    required this.identity,
    required this.reference,
    required this.humanContext,
    required this.meaning,
    required this.emphasis,
    this.ownerDestination,
    this.whyNow,
    this.whyNowReason,
    this.serverState,
    this.consequence,
    this.consequenceState,
    this.turn,
    this.responseType,
    this.responseLabel,
    this.responseCapability,
    this.metadata = const [],
    this.mediaRef,
    this.freshness = MakoloFreshnessCue.unknown,
  });

  final String identity;
  final StructuredDestination reference;
  final String humanContext;
  final String meaning;
  final String? whyNow;
  final String? whyNowReason;
  final String? serverState;
  final String? consequence;
  final String? consequenceState;
  final String? turn;
  final String? responseType;
  final NowPresentationEmphasis emphasis;
  final String? responseLabel;
  final String? responseCapability;
  final List<String> metadata;
  final String? mediaRef;
  final MakoloFreshnessCue freshness;
  final StructuredDestination? ownerDestination;
}
