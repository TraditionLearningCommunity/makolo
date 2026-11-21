import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/runtime_close_barrier.dart';

void main() {
  test(
    'replacement waits for database close, without touching its contents',
    () async {
      final gate = RuntimeCloseBarrier();
      final finishClose = Completer<void>();
      final steps = <String>[];
      final first = gate.open(() async {
        steps.add('open-public-and-profile-a');
        return 'profile-a';
      });
      expect(await first, 'profile-a');
      gate.release(first, (value) async {
        steps.add('close-$value-start');
        await finishClose.future;
        steps.add('close-$value-end');
      });

      final second = gate.open(() async {
        steps.add('open-public-and-profile-b');
        return 'profile-b';
      });
      await Future<void>.delayed(Duration.zero);
      expect(steps, ['open-public-and-profile-a', 'close-profile-a-start']);
      finishClose.complete();
      expect(await second, 'profile-b');
      expect(steps, [
        'open-public-and-profile-a',
        'close-profile-a-start',
        'close-profile-a-end',
        'open-public-and-profile-b',
      ]);
      gate.release(second, (value) async => steps.add('close-$value'));
    },
  );

  test(
    'disposed pending initialization is closed before another open',
    () async {
      final gate = RuntimeCloseBarrier();
      final constructed = Completer<String>();
      final steps = <String>[];
      final first = gate.open(() => constructed.future);
      gate.release(first, (value) async => steps.add('closed-$value'));
      final second = gate.open(() async {
        steps.add('opened-second');
        return 'second';
      });
      await Future<void>.delayed(Duration.zero);
      expect(steps, isEmpty);
      constructed.complete('first');
      expect(await second, 'second');
      expect(steps, ['closed-first', 'opened-second']);
      gate.release(second, (value) async => steps.add('closed-$value'));
    },
  );

  test('failed initialization does not prevent a replacement', () async {
    final gate = RuntimeCloseBarrier();
    final failed = gate.open<String>(() async => throw StateError('init'));
    gate.release(failed, (_) async => fail('No runtime exists to close'));
    await expectLater(failed, throwsStateError);
    final replacement = await gate.open(() async => 'guest');
    expect(replacement, 'guest');
  });

  test('failed close is not bypassed by a new runtime', () async {
    final gate = RuntimeCloseBarrier();
    final first = gate.open(() async => 'old');
    await first;
    gate.release(first, (_) async => throw StateError('close failed'));
    await expectLater(gate.open(() async => 'must-not-open'), throwsStateError);
  });
}
