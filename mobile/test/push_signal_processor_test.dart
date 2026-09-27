import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/platform/notifications/push_signal.dart';
import 'package:makolo_mobile/platform/notifications/push_signal_processor.dart';

void main() {
  test('push signal invalidates sources before owner refresh', () async {
    final order = <String>[];
    final processor = PushSignalProcessor(
      normalize: (signal) async {
        expect(signal.data['kind'], 'journey.changed');
        return const NormalizedPushSignal(
          sourceKeys: {'now', 'ongoing'},
          destination: StructuredDestination(kind: 'Journey', id: 'journey-a'),
        );
      },
      invalidate: (sourceKey) async {
        order.add('invalidate:$sourceKey');
      },
      refresh: (sourceKeys) async {
        order.add('refresh:${sourceKeys.toList()..sort()}');
      },
    );

    final result = await processor.process(
      const PushSignal(data: {'kind': 'journey.changed'}),
    );

    expect(result?.destination?.id, 'journey-a');
    expect(order.take(2), everyElement(startsWith('invalidate:')));
    expect(order.last, startsWith('refresh:'));
  });

  test('invalid signal performs no local mutation', () async {
    var invalidated = false;
    var refreshed = false;
    final processor = PushSignalProcessor(
      normalize: (_) async => null,
      invalidate: (_) async => invalidated = true,
      refresh: (_) async => refreshed = true,
    );

    expect(
      await processor.process(const PushSignal(data: {'unknown': 'value'})),
      isNull,
    );
    expect(invalidated, isFalse);
    expect(refreshed, isFalse);
  });
}
