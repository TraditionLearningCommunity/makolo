import '../design/surface_states.dart';
import '../selectors/projection_selector.dart';
import '../sync/freshness.dart';

/// Small integration boundary from KA selection to EF presentation.
///
/// Availability remains explicit because a missing local projection is not the
/// same thing as a confirmed empty collection. Authority is supplied by the
/// relevant owner/capability and is never inferred here.
class ProjectionSurfaceAdapter {
  const ProjectionSurfaceAdapter();

  MakoloSurfacePresentation adapt({
    required ProjectionPresentationModel projection,
    required MakoloAvailabilityCue availability,
    required ReachabilityState reachability,
    MakoloAuthorityCue authority = MakoloAuthorityCue.unknown,
    MakoloCommitCue? commit,
    MakoloFailureCue failure = MakoloFailureCue.none,
    bool refreshing = false,
  }) {
    return MakoloSurfacePresentation(
      availability: availability,
      freshness: freshnessCue(projection.freshness),
      reachability: reachabilityCue(reachability),
      authority: authority,
      commit:
          commit ??
          (projection.hasPending
              ? MakoloCommitCue.pending
              : MakoloCommitCue.none),
      failure: failure,
      refreshing: refreshing,
    );
  }

  MakoloFreshnessCue freshnessCue(FreshnessState? freshness) {
    return switch (freshness) {
      null => MakoloFreshnessCue.unknown,
      FreshnessState.fresh => MakoloFreshnessCue.current,
      FreshnessState.usableButOld => MakoloFreshnessCue.oldObservation,
      FreshnessState.refreshRecommended => MakoloFreshnessCue.refreshRecommended,
      FreshnessState.revalidationRequired =>
        MakoloFreshnessCue.revalidationRequired,
      FreshnessState.expired => MakoloFreshnessCue.expired,
    };
  }

  MakoloReachabilityCue reachabilityCue(ReachabilityState reachability) {
    return switch (reachability) {
      ReachabilityState.unknown => MakoloReachabilityCue.unknown,
      ReachabilityState.reachable => MakoloReachabilityCue.reachable,
      ReachabilityState.unreachable =>
        MakoloReachabilityCue.temporarilyUnavailable,
    };
  }
}
