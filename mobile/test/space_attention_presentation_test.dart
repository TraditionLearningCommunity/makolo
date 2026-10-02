import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/space/space_attention_presentation.dart';
import 'package:makolo_mobile/sync/freshness.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';

StoredProjection _projection({
  Map<String, dynamic>? payload,
  DateTime? receivedAt,
}) {
  return StoredProjection(
    kind: 'space.now',
    schemaVersion: 1,
    payload:
        payload ??
        {
          'selection': {
            'state': 'unavailable',
            'reason': 'no_safe_selection_contract',
          },
          'items': <Object>[],
          'has_more': false,
        },
    receivedAt: receivedAt ?? DateTime.utc(2026, 10, 2, 12),
  );
}

void main() {
  final now = DateTime.utc(2026, 10, 2, 12);

  test('canonical unavailable is not interpreted as empty or failure', () {
    final presentation = SpaceAttentionPresentation.resolve(
      projection: _projection(),
      source: const OwnerSourceState(
        lastSuccessAt: null,
      ),
      now: now,
    );

    expect(presentation.state, SpaceAttentionState.unavailable);
    expect(presentation.hasRefreshFailure, isFalse);
  });

  test('offline failure preserves an unavailable snapshot as knowledge', () {
    final presentation = SpaceAttentionPresentation.resolve(
      projection: _projection(),
      source: OwnerSourceState(
        lastSuccessAt: now.subtract(const Duration(minutes: 20)),
        lastErrorCode: 'transport_error',
      ),
      now: now,
    );

    expect(presentation.state, SpaceAttentionState.unavailable);
    expect(presentation.hasRefreshFailure, isTrue);
  });

  test('offline without a snapshot is a recoverable failure', () {
    final presentation = SpaceAttentionPresentation.resolve(
      projection: null,
      source: const OwnerSourceState(lastErrorCode: 'transport_error'),
      now: now,
    );

    expect(presentation.state, SpaceAttentionState.failure);
  });

  test('invalidated source never revives the cached projection', () {
    final presentation = SpaceAttentionPresentation.resolve(
      projection: _projection(),
      source: const OwnerSourceState(
        invalidated: true,
        lastErrorCode: 'not_found',
      ),
      now: now,
    );

    expect(presentation.state, SpaceAttentionState.failure);
  });

  test('malformed and unsupported wire states do not invent calm states', () {
    final malformed = SpaceAttentionPresentation.resolve(
      projection: _projection(
        payload: {'items': <Object>[], 'has_more': false},
      ),
      source: OwnerSourceState.unknown,
      now: now,
    );
    final unsupportedEmpty = SpaceAttentionPresentation.resolve(
      projection: _projection(
        payload: {
          'selection': {'state': 'empty'},
          'items': <Object>[],
          'has_more': false,
        },
      ),
      source: OwnerSourceState.unknown,
      now: now,
    );
    final impossibleContent = SpaceAttentionPresentation.resolve(
      projection: _projection(
        payload: {
          'selection': {'state': 'unavailable'},
          'items': [
            {'id': 'invented'},
          ],
          'has_more': false,
        },
      ),
      source: OwnerSourceState.unknown,
      now: now,
    );

    expect(malformed.state, SpaceAttentionState.failure);
    expect(unsupportedEmpty.state, SpaceAttentionState.failure);
    expect(impossibleContent.state, SpaceAttentionState.failure);
  });

  test('old unavailable knowledge stays visible with freshness caution', () {
    final presentation = SpaceAttentionPresentation.resolve(
      projection: _projection(
        receivedAt: now.subtract(const Duration(hours: 7)),
      ),
      source: OwnerSourceState.unknown,
      now: now,
    );

    expect(presentation.state, SpaceAttentionState.unavailable);
    expect(presentation.freshness, FreshnessState.usableButOld);
    expect(presentation.needsFreshnessCaution, isTrue);
  });
}