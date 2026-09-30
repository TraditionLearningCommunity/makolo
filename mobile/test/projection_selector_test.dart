import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/selectors/projection_selector.dart';
import 'package:makolo_mobile/sync/freshness.dart';

void main() {
  test(
    'selector deterministically composes local knowledge without authority',
    () {
      final now = DateTime.utc(2026, 9, 30, 8);
      final projection = StoredProjection(
        kind: 'personal.journey.detail',
        resourceKey: 'journey-1',
        schemaVersion: 1,
        payload: const {'status': 'server-owned'},
        receivedAt: now.subtract(const Duration(hours: 2)),
        lastVerifiedOnlineAt: now.subtract(const Duration(hours: 2)),
      );
      const policy = FreshnessPolicy(
        id: 'journey-contextual',
        refreshRecommendedAfter: Duration(hours: 1),
      );
      const selector = ProjectionSelector();

      final result = selector.select(
        projection: projection,
        freshnessPolicy: policy,
        now: now,
        resources: const [
          ResourceReference(
            kind: 'Proof',
            id: 'proof-2',
            projectionKind: 'personal.journey.detail',
          ),
          ResourceReference(
            kind: 'Activity',
            id: 'activity-1',
            projectionKind: 'personal.journey.detail',
          ),
        ],
        drafts: [
          DraftReference(
            draftId: 'draft-old',
            resourceKind: 'Form',
            updatedAt: now.subtract(const Duration(minutes: 5)),
          ),
          DraftReference(
            draftId: 'draft-new',
            resourceKind: 'Form',
            updatedAt: now,
          ),
        ],
        pendingOperations: const [
          PendingOperationReference(
            operationId: 'op-b',
            operationKind: 'form.save',
            state: 'queued',
          ),
          PendingOperationReference(
            operationId: 'op-a',
            operationKind: 'upload',
            state: 'in_flight',
          ),
        ],
      );

      expect(result.available, isTrue);
      expect(result.payload?['status'], 'server-owned');
      expect(result.freshness, FreshnessState.refreshRecommended);
      expect(result.resources.map((item) => item.id), [
        'activity-1',
        'proof-2',
      ]);
      expect(result.drafts.map((item) => item.draftId), [
        'draft-new',
        'draft-old',
      ]);
      expect(result.pendingOperations.map((item) => item.operationId), [
        'op-a',
        'op-b',
      ]);
      expect(result.hasPending, isTrue);
    },
  );

  test('selector exposes revalidation without inventing a local decision', () {
    final now = DateTime.utc(2026, 9, 30, 8);
    final projection = StoredProjection(
      kind: 'personal.access.detail',
      resourceKey: 'access-1',
      schemaVersion: 1,
      payload: const {'valid': true},
      receivedAt: now,
    );
    const selector = ProjectionSelector();
    const policy = FreshnessPolicy(
      id: 'access-critical',
      revalidateBeforeAction: true,
    );

    final result = selector.select(
      projection: projection,
      freshnessPolicy: policy,
      now: now,
      forAction: true,
    );

    expect(result.payload?['valid'], isTrue);
    expect(result.freshness, FreshnessState.revalidationRequired);
  });
}
