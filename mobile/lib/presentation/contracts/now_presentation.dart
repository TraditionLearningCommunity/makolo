import '../../design/surface_states.dart';
import '../../navigation/destination.dart';

enum NowPresentationEmphasis { primary, secondary }

enum NowContinuationState { more, end, unknown }

enum NowMediaPurpose { recognize, understand, establish, prepare, act, unknown }

enum NowMediaTarget {
  situation,
  subject,
  humanContext,
  state,
  delta,
  turn,
  makoloPreparation,
  action,
  unknown,
}

enum NowMediaKind { image, pdf, document, video, audio, coordinates, unknown }

enum NowInteractionDepth { directNow, focused, domainDepth, none, unknown }

class NowContinuationPresentation {
  const NowContinuationPresentation({required this.state, this.token});

  final NowContinuationState state;
  final String? token;
}

class NowBusinessActionPresentation {
  const NowBusinessActionPresentation({
    required this.capability,
    required this.label,
    required this.interactionDepth,
    this.href,
    this.presentationRank,
  });

  final String capability;
  final String label;
  final NowInteractionDepth interactionDepth;
  final String? href;
  final String? presentationRank;

  bool get isPresentationAction =>
      capability.trim().isNotEmpty && label.trim().isNotEmpty;

  bool get canDominate =>
      isPresentationAction &&
      interactionDepth != NowInteractionDepth.domainDepth &&
      interactionDepth != NowInteractionDepth.none &&
      interactionDepth != NowInteractionDepth.unknown;
}

class NowMediaBindingPresentation {
  const NowMediaBindingPresentation({
    required this.resourceRef,
    required this.target,
    required this.purpose,
    required this.kind,
    this.mimeType,
    this.url,
    this.downloadUrl,
    this.localPath,
    this.label,
    this.aspect,
    this.cached = false,
    this.authorized = false,
    this.presentationRank,
  });

  final String resourceRef;
  final NowMediaTarget target;
  final NowMediaPurpose purpose;
  final NowMediaKind kind;
  final String? mimeType;
  final String? url;
  final String? downloadUrl;
  final String? localPath;
  final String? label;
  final String? aspect;
  final bool cached;
  final bool authorized;
  final String? presentationRank;

  bool get canRender => authorized && resourceRef.trim().isNotEmpty;

  bool get canDominate =>
      canRender &&
      (presentationRank == 'primary' ||
          purpose == NowMediaPurpose.understand ||
          purpose == NowMediaPurpose.establish ||
          purpose == NowMediaPurpose.act);
}

class NowRelationMemberPresentation {
  const NowRelationMemberPresentation({
    required this.id,
    required this.label,
    this.subtext,
    this.knowledgeState,
  });

  final String id;
  final String label;
  final String? subtext;
  final String? knowledgeState;
}

class NowRelationPresentation {
  const NowRelationPresentation({
    required this.kind,
    required this.memberIds,
    this.summary,
  });

  final String kind;
  final List<String> memberIds;
  final String? summary;
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
    this.turnLabel,
    this.responseType,
    this.responseLabel,
    this.responseCapability,
    this.horizon,
    this.metadata = const [],
    this.mediaRef,
    this.mediaBindings = const [],
    this.businessActions = const [],
    this.relationMembers = const [],
    this.relations = const [],
    this.makoloPreparation = const [],
    this.knowledgeState,
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
  final String? turnLabel;
  final String? responseType;
  final NowPresentationEmphasis emphasis;
  final String? responseLabel;
  final String? responseCapability;
  final String? horizon;
  final List<String> metadata;
  final String? mediaRef;
  final List<NowMediaBindingPresentation> mediaBindings;
  final List<NowBusinessActionPresentation> businessActions;
  final List<NowRelationMemberPresentation> relationMembers;
  final List<NowRelationPresentation> relations;
  final List<String> makoloPreparation;
  final String? knowledgeState;
  final MakoloFreshnessCue freshness;
  final StructuredDestination? ownerDestination;
}
