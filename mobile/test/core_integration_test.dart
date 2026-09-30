import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/presentation/projection_surface_adapter.dart';
import 'package:makolo_mobile/selectors/projection_selector.dart';
import 'package:makolo_mobile/sync/freshness.dart';

void main() {
  const adapter = ProjectionSurfaceAdapter();

  ProjectionPresentationModel model({
    FreshnessState? freshness,
    bool pending = false,
  }) {
    return ProjectionPresentationModel(
      available: true,
      payload: const {'id': 'resource-1'},
      freshness: freshness,
      resources: const [],
      drafts: const [],
      pendingOperations: pending
          ? const [
              PendingOperationReference(
                operationId: 'operation-1',
                operationKind: 'resource.update',
                state: 'queued',
              ),
            ]
          : const [],
    );
  }

  test('KA freshness maps explicitly into EF cues', () {
    expect(adapter.freshnessCue(null), MakoloFreshnessCue.unknown);
    expect(
      adapter.freshnessCue(FreshnessState.fresh),
      MakoloFreshnessCue.current,
    );
    expect(
      adapter.freshnessCue(FreshnessState.usableButOld),
      MakoloFreshnessCue.oldObservation,
    );
    expect(
      adapter.freshnessCue(FreshnessState.refreshRecommended),
      MakoloFreshnessCue.refreshRecommended,
    );
    expect(
      adapter.freshnessCue(FreshnessState.revalidationRequired),
      MakoloFreshnessCue.revalidationRequired,
    );
    expect(
      adapter.freshnessCue(FreshnessState.expired),
      MakoloFreshnessCue.expired,
    );
  });

  test('KA reachability preserves unknown instead of assuming reachable', () {
    expect(
      adapter.reachabilityCue(ReachabilityState.unknown),
      MakoloReachabilityCue.unknown,
    );
    expect(
      adapter.reachabilityCue(ReachabilityState.reachable),
      MakoloReachabilityCue.reachable,
    );
    expect(
      adapter.reachabilityCue(ReachabilityState.unreachable),
      MakoloReachabilityCue.temporarilyUnavailable,
    );
  });

  test('availability remains caller-owned and can distinguish not acquired', () {
    final notAcquired = ProjectionPresentationModel(
      available: false,
      payload: null,
      freshness: null,
      resources: const [],
      drafts: const [],
      pendingOperations: const [],
    );

    final initial = adapter.adapt(
      projection: notAcquired,
      availability: MakoloAvailabilityCue.initial,
      reachability: ReachabilityState.unknown,
    );
    final confirmedEmpty = adapter.adapt(
      projection: notAcquired,
      availability: MakoloAvailabilityCue.empty,
      reachability: ReachabilityState.reachable,
    );

    expect(initial.availability, MakoloAvailabilityCue.initial);
    expect(initial.freshness, MakoloFreshnessCue.unknown);
    expect(confirmedEmpty.availability, MakoloAvailabilityCue.empty);
  });

  test('pending content is never adapted as confirmed', () {
    final state = adapter.adapt(
      projection: model(
        freshness: FreshnessState.fresh,
        pending: true,
      ),
      availability: MakoloAvailabilityCue.content,
      reachability: ReachabilityState.reachable,
    );

    expect(state.commit, MakoloCommitCue.pending);
    expect(state.commit, isNot(MakoloCommitCue.confirmed));
  });

  test('content can coexist with unreachable and refresh states', () {
    final state = adapter.adapt(
      projection: model(freshness: FreshnessState.usableButOld),
      availability: MakoloAvailabilityCue.content,
      reachability: ReachabilityState.unreachable,
      refreshing: true,
    );

    expect(state.availability, MakoloAvailabilityCue.content);
    expect(state.freshness, MakoloFreshnessCue.oldObservation);
    expect(
      state.reachability,
      MakoloReachabilityCue.temporarilyUnavailable,
    );
    expect(state.refreshing, isTrue);
  });

  test('authority is passed through and never inferred from KA state', () {
    final unknown = adapter.adapt(
      projection: model(freshness: FreshnessState.fresh),
      availability: MakoloAvailabilityCue.content,
      reachability: ReachabilityState.reachable,
    );
    final requiresOwner = adapter.adapt(
      projection: model(freshness: FreshnessState.fresh),
      availability: MakoloAvailabilityCue.content,
      reachability: ReachabilityState.reachable,
      authority: MakoloAuthorityCue.remoteConfirmationRequired,
    );

    expect(unknown.authority, MakoloAuthorityCue.unknown);
    expect(
      requiresOwner.authority,
      MakoloAuthorityCue.remoteConfirmationRequired,
    );
  });
}
