import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/search/progressive_search_coordinator.dart';

void main() {
  test('debounces typing and only executes the last stable query', () async {
    final calls = <int>[];
    final coordinator = ProgressiveSearchCoordinator(
      debounce: const Duration(milliseconds: 15),
      onSearch: (revision) async {
        calls.add(revision);
      },
    );
    coordinator.changed();
    coordinator.changed();
    coordinator.changed();
    await Future<void>.delayed(const Duration(milliseconds: 40));
    expect(calls, [3]);
    coordinator.dispose();
  });

  test('older requests cannot replace the current result', () async {
    final first = Completer<void>();
    final accepted = <int>[];
    late ProgressiveSearchCoordinator coordinator;
    coordinator = ProgressiveSearchCoordinator(
      onSearch: (revision) async {
        if (revision == 1) await first.future;
        if (coordinator.isCurrent(revision)) accepted.add(revision);
      },
    );
    coordinator.changed(immediate: true);
    coordinator.changed(immediate: true);
    first.complete();
    await Future<void>.delayed(Duration.zero);
    expect(accepted, [2]);
    coordinator.dispose();
  });

  test('refresh and disposal invalidate queued callbacks', () async {
    final calls = <int>[];
    final coordinator = ProgressiveSearchCoordinator(
      debounce: const Duration(milliseconds: 10),
      onSearch: (revision) async {
        calls.add(revision);
      },
    );
    coordinator.changed();
    await coordinator.refresh();
    coordinator.changed();
    coordinator.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 30));
    expect(calls, [2]);
  });
}
