import 'dart:async';

import '../navigation/incoming_intent.dart';

class RuntimeIngress {
  RuntimeIngress();

  final StreamController<IncomingIntent> _controller =
      StreamController<IncomingIntent>.broadcast();

  Stream<IncomingIntent> get intents => _controller.stream;

  void add(IncomingIntent intent) => _controller.add(intent);

  Future<void> close() => _controller.close();
}
