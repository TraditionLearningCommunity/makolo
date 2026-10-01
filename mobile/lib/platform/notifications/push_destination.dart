import '../../navigation/destination.dart';
import '../../navigation/incoming_intent.dart';
import '../../navigation/structured_destination_codec.dart';
import 'push_signal.dart';

class PushDestinationResolver {
  const PushDestinationResolver({
    this.codec = const StructuredDestinationCodec(),
  });

  final StructuredDestinationCodec codec;

  StructuredDestination? destination(PushSignal signal) {
    final encoded = signal.data['destination'];
    if (encoded == null || encoded.isEmpty) return null;
    return codec.fromJson(encoded);
  }

  IncomingIntent? intent(PushSignal signal) {
    final value = destination(signal);
    if (value == null) return null;
    return IncomingIntent(
      source: IncomingIntentSource.push,
      destination: value,
    );
  }
}
