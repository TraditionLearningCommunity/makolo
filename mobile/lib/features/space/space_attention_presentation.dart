import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'space_repository.dart';

enum SpaceAttentionState { initial, unavailable, failure }

class SpaceAttentionPresentation {
  const SpaceAttentionPresentation({
    required this.state,
    required this.source,
    this.freshness,
  });

  final SpaceAttentionState state;
  final OwnerSourceState source;
  final FreshnessState? freshness;

  bool get hasRefreshFailure =>
      source.reachability == ReachabilityState.unreachable;

  bool get needsFreshnessCaution =>
      freshness == FreshnessState.usableButOld ||
      freshness == FreshnessState.revalidationRequired ||
      freshness == FreshnessState.expired;

  static SpaceAttentionPresentation resolve({
    required StoredProjection? projection,
    required OwnerSourceState source,
    required DateTime now,
  }) {
    if (source.invalidated) {
      return SpaceAttentionPresentation(
        state: SpaceAttentionState.failure,
        source: source,
      );
    }

    if (projection == null) {
      return SpaceAttentionPresentation(
        state: source.lastErrorCode == null
            ? SpaceAttentionState.initial
            : SpaceAttentionState.failure,
        source: source,
      );
    }

    final payload = projection.payload;
    final selection = payload['selection'];
    final items = payload['items'];
    final hasMore = payload['has_more'];
    if (selection is! Map || items is! List || hasMore is! bool) {
      return SpaceAttentionPresentation(
        state: SpaceAttentionState.failure,
        source: source,
      );
    }

    final selectionState = selection['state'];
    if (selectionState != 'unavailable' || items.isNotEmpty || hasMore) {
      return SpaceAttentionPresentation(
        state: SpaceAttentionState.failure,
        source: source,
      );
    }

    return SpaceAttentionPresentation(
      state: SpaceAttentionState.unavailable,
      source: source,
      freshness: WorkspaceContextRepository.surfaceFreshness.evaluate(
        projection,
        now: now,
        invalidated: source.invalidated,
      ),
    );
  }
}
