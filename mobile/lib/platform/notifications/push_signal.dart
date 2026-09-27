import 'package:firebasemessaging/firebasemessaging.dart';

class PushSignal {
  const PushSignal({required this.data, this.messageId, this.sentAt});

  final Map<String, String> data;
  final String? messageId;
  final DateTime? sentAt;
}

abstract interface class PushSignalReceiver {
  Stream<PushSignal> get foregroundSignals;
  Stream<PushSignal> get openedSignals;
  Future<PushSignal?> initialSignal();
}

class FirebasePushSignalReceiver implements PushSignalReceiver {
  FirebasePushSignalReceiver({required this.messaging});

  final FirebaseMessaging messaging;

  @override
  Stream<PushSignal> get foregroundSignals =>
      FirebaseMessaging.onMessage.map(_signal);

  @override
  Stream<PushSignal> get openedSignals =>
      FirebaseMessaging.onMessageOpenedApp.map(_signal);

  @override
  Future<PushSignal?> initialSignal() async {
    final message = await messaging.getInitialMessage();
    return message == null ? null : _signal(message);
  }

  PushSignal _signal(RemoteMessage message) {
    return PushSignal(
      data: message.data.map((key, value) => MapEntry(key, value.toString())),
      messageId: message.messageId,
      sentAt: message.sentTime,
    );
  }
}
