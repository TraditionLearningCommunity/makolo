import '../../sync/freshness.dart';

/// Scope and time checks for cached Jour J / Live snapshots.
///
/// The canonical owner remains the source of truth. Offline content can only
/// be presented as last-known knowledge; it never grants an action or a role.
final class OccurrenceContinuity {
  const OccurrenceContinuity._();

  static bool matches({
    required Map<String, dynamic> payload,
    required String occurrenceId,
    required String profileId,
    String? actorSpaceId,
    required String surface,
  }) {
    final identity = payload['identity'];
    final context = payload['context'];
    if (identity is! Map || context is! Map) return false;
    final scope = context['occurrence'];
    return identity['kind'] == 'occurrence' &&
        identity['id']?.toString() == occurrenceId &&
        scope is Map &&
        scope['id']?.toString() == occurrenceId &&
        context['viewer_profile_id']?.toString() == profileId &&
        context['actor_space_id']?.toString() == actorSpaceId &&
        payload['surface'] == surface;
  }

  static bool liveWindowEnded(
    Map<String, dynamic> payload, {
    required DateTime now,
  }) {
    final phase = payload['phase'];
    if (phase == 'after' || phase == 'cancelled') return true;
    final context = payload['context'];
    if (context is Map) {
      final occurrence = context['occurrence'];
      if (occurrence is Map &&
          const {'cancelled', 'completed'}.contains(occurrence['state'])) {
        return true;
      }
    }
    final live = payload['live'];
    if (live is! Map || live['available'] != true) return true;
    final raw = live['ends_at'];
    if (raw is! String || raw.isEmpty) return false;
    final end = DateTime.tryParse(raw);
    return end != null && !now.toUtc().isBefore(end.toUtc());
  }

  /// After switching actor, never revive a previous privileged snapshot
  /// before a successful owner reconciliation for that newly active context.
  static bool verifiedAfterActorSwitch({
    required DateTime? lastSuccessAt,
    required DateTime? actorSwitchedAt,
  }) => actorSwitchedAt == null ||
      (lastSuccessAt != null &&
          !lastSuccessAt.toUtc().isBefore(actorSwitchedAt.toUtc()));

  static bool canOfferActions({
    required bool sourceInvalidated,
    required ReachabilityState reachability,
    required FreshnessState? freshness,
    required bool systemOffline,
    required bool liveEnded,
  }) {
    if (sourceInvalidated || systemOffline || liveEnded ||
        reachability != ReachabilityState.reachable) {
      return false;
    }
    return freshness == FreshnessState.fresh ||
        freshness == FreshnessState.refreshRecommended;
  }

  static bool isDenied(String? code) =>
      code == 'permission_denied' || code == 'not_found';
}
