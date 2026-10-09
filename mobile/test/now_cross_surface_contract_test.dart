import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/now/now_screen.dart';
import 'package:makolo_mobile/features/now/now_selector.dart';

void main() {
  test('shared server semantics select S1-S5 identically on Flutter', () {
    final fixture =
        jsonDecode(File('test/fixtures/now_s1_s5_contract.json').readAsStringSync())
            as Map<String, dynamic>;
    final projection = StoredProjection(
      kind: 'personal.now',
      schemaVersion: 1,
      payload: fixture,
      receivedAt: DateTime.utc(2026, 10, 9, 9),
      freshUntil: DateTime.utc(2026, 10, 10),
    );
    final selection = const NowSelector().select(
      projection: projection,
      now: DateTime.utc(2026, 10, 9, 10),
    );
    expect(selection.situations.length, 5);
    expect(
      selection.situations.map(topologyFor).toList(),
      [
        NowTopology.meaning,
        NowTopology.media,
        NowTopology.action,
        NowTopology.waiting,
        NowTopology.composition,
      ],
    );
  });
}
