import '../data/local/profile_store.dart';

enum FreshnessState {
  fresh('fresh'),
  usableButOld('usable_but_old'),
  refreshRecommended('refresh_recommended'),
  revalidationRequired('revalidation_required'),
  expired('expired');

  const FreshnessState(this.wireValue);
  final String wireValue;
}

enum ReachabilityState { unknown, reachable, unreachable }

class FreshnessPolicy {
  const FreshnessPolicy({
    required this.id,
    this.refreshRecommendedAfter,
    this.usableButOldAfter,
    this.revalidateBeforeAction = false,
    this.revalidateAfterFreshUntil = false,
  });

  final String id;
  final Duration? refreshRecommendedAfter;
  final Duration? usableButOldAfter;
  final bool revalidateBeforeAction;
  final bool revalidateAfterFreshUntil;

  FreshnessState evaluate(
    StoredProjection projection, {
    required DateTime now,
    bool forAction = false,
    bool invalidated = false,
  }) {
    final instant = now.toUtc();
    final expiresAt = projection.expiresAt?.toUtc();
    if (expiresAt != null && !instant.isBefore(expiresAt)) {
      return FreshnessState.expired;
    }

    if (forAction && revalidateBeforeAction) {
      return FreshnessState.revalidationRequired;
    }

    final freshUntil = projection.freshUntil?.toUtc();
    if (freshUntil != null && !instant.isBefore(freshUntil)) {
      return revalidateAfterFreshUntil
          ? FreshnessState.revalidationRequired
          : FreshnessState.refreshRecommended;
    }

    if (invalidated) {
      return FreshnessState.refreshRecommended;
    }

    final basis =
        projection.sourceUpdatedAt?.toUtc() ??
        projection.sourceGeneratedAt?.toUtc() ??
        projection.lastVerifiedOnlineAt?.toUtc() ??
        projection.receivedAt.toUtc();
    final age = instant.difference(basis);
    final oldAfter = usableButOldAfter;
    if (oldAfter != null && age >= oldAfter) {
      return FreshnessState.usableButOld;
    }
    final refreshAfter = refreshRecommendedAfter;
    if (refreshAfter != null && age >= refreshAfter) {
      return FreshnessState.refreshRecommended;
    }
    return FreshnessState.fresh;
  }
}

ReachabilityState reachabilityFromSource({
  required DateTime? lastSuccessAt,
  required String? lastErrorCode,
}) {
  if (lastErrorCode != null && lastErrorCode.isNotEmpty) {
    return ReachabilityState.unreachable;
  }
  if (lastSuccessAt != null) {
    return ReachabilityState.reachable;
  }
  return ReachabilityState.unknown;
}
