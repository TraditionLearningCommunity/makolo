import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_screens.dart';

void main() {
  StoredProjection position(Map<String, dynamic> payload) => StoredProjection(
    kind: 'discovery.presentation-position',
    schemaVersion: 1,
    payload: payload,
    receivedAt: DateTime.utc(2026, 10, 30),
  );

  test('a received Discovery position restores the same opaque cursor', () {
    final restored = retainedDiscoveryPosition(
      position({'page': 2, 'continuation': 'signed-server-token'}),
    );
    expect(restored?.page, 2);
    expect(restored?.continuation, 'signed-server-token');
  });

  test(
    'a page-one return restores scroll and focused candidate independently',
    () {
      final marker = position({
        'page': 1,
        'continuation': null,
        'scroll_offset': 528.0,
        'selected_candidate_key': 'activity:chosen',
      });
      expect(retainedDiscoveryPosition(marker), isNull);
      expect(retainedDiscoveryScrollOffset(marker), 528.0);
      expect(retainedDiscoveryFocusedCandidate(marker), 'activity:chosen');
    },
  );

  test(
    'malformed position hints are rejected without exposing a candidate',
    () {
      expect(
        retainedDiscoveryScrollOffset(position({'scroll_offset': -20})),
        isNull,
      );
      expect(
        retainedDiscoveryScrollOffset(position({'scroll_offset': 'infinite'})),
        isNull,
      );
      expect(
        retainedDiscoveryFocusedCandidate(
          position({'selected_candidate_key': ''}),
        ),
        isNull,
      );
      expect(
        retainedDiscoveryFocusedCandidate(
          position({'selected_candidate_key': 42}),
        ),
        isNull,
      );
      final foreignKind = StoredProjection(
        kind: 'other',
        schemaVersion: 1,
        payload: const {'scroll_offset': 55, 'selected_candidate_key': 'x'},
        receivedAt: DateTime.utc(2026, 10, 30),
      );
      expect(retainedDiscoveryScrollOffset(foreignKind), isNull);
      expect(retainedDiscoveryFocusedCandidate(foreignKind), isNull);
    },
  );

  test('missing or malformed cursors cannot become new Discovery data', () {
    expect(retainedDiscoveryPosition(null), isNull);
    expect(
      retainedDiscoveryPosition(position({'page': 1, 'continuation': 'old'})),
      isNull,
    );
    expect(
      retainedDiscoveryPosition(position({'page': 3, 'continuation': ''})),
      isNull,
    );
    expect(
      retainedDiscoveryPosition(
        position({'page': 'not-a-page', 'continuation': 'x'}),
      ),
      isNull,
    );
  });
}
