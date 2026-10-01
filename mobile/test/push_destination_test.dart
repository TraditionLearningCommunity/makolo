import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/navigation/structured_destination_codec.dart';
import 'package:makolo_mobile/platform/notifications/push_destination.dart';
import 'package:makolo_mobile/platform/notifications/push_signal.dart';

void main() {
  const resolver = PushDestinationResolver();
  const codec = StructuredDestinationCodec();

  test('opened push reuses StructuredDestination codec', () {
    final signal = PushSignal(
      data: {
        'destination': codec.toJson(
          const StructuredDestination(kind: 'Journey', id: 'journey-1'),
        ),
      },
    );
    expect(resolver.intent(signal)?.destination.id, 'journey-1');
  });

  test('invalid push destination is ignored', () {
    expect(
      resolver.intent(const PushSignal(data: {'destination': '{invalid'})),
      isNull,
    );
  });
}
