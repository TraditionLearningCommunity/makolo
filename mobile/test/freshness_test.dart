import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/sync/freshness.dart';

void main() {
  final observedAt = DateTime.utc(2026, 9, 30, 6);

  StoredProjection projection({DateTime? freshUntil, DateTime? expiresAt}) {
    return StoredProjection(
      kind: 'test.detail',
      resourceKey: '42',
      schemaVersion: 1,
      payload: const {'id': '42'},
      receivedAt: observedAt,
      lastVerifiedOnlineAt: observedAt,
      freshUntil: freshUntil,
      expiresAt: expiresAt,
    );
  }

  test('freshness transitions are source-policy driven', () {
    const policy = FreshnessPolicy(
      id: 'test-swr',
      refreshRecommendedAfter: Duration(minutes: 10),
      usableButOldAfter: Duration(hours: 1),
    );

    expect(
      policy.evaluate(
        projection(),
        now: observedAt.add(const Duration(minutes: 5)),
      ),
      FreshnessState.fresh,
    );
    expect(
      policy.evaluate(
        projection(),
        now: observedAt.add(const Duration(minutes: 20)),
      ),
      FreshnessState.refreshRecommended,
    );
    expect(
      policy.evaluate(
        projection(),
        now: observedAt.add(const Duration(hours: 2)),
      ),
      FreshnessState.usableButOld,
    );
  });

  test('revalidation requirement is independent from data availability', () {
    const policy = FreshnessPolicy(
      id: 'access-critical',
      revalidateBeforeAction: true,
    );
    final stored = projection();

    expect(
      policy.evaluate(stored, now: observedAt, forAction: false),
      FreshnessState.fresh,
    );
    expect(
      policy.evaluate(stored, now: observedAt, forAction: true),
      FreshnessState.revalidationRequired,
    );
  });

  test('server expiry is terminal for current-state use', () {
    const policy = FreshnessPolicy(id: 'server-bounded');
    expect(
      policy.evaluate(
        projection(expiresAt: observedAt.add(const Duration(minutes: 15))),
        now: observedAt.add(const Duration(minutes: 16)),
      ),
      FreshnessState.expired,
    );
  });

  test('reachability is independent from freshness', () {
    expect(
      reachabilityFromSource(lastSuccessAt: null, lastErrorCode: null),
      ReachabilityState.unknown,
    );
    expect(
      reachabilityFromSource(lastSuccessAt: observedAt, lastErrorCode: null),
      ReachabilityState.reachable,
    );
    expect(
      reachabilityFromSource(
        lastSuccessAt: observedAt,
        lastErrorCode: 'offline',
      ),
      ReachabilityState.unreachable,
    );
  });
}
