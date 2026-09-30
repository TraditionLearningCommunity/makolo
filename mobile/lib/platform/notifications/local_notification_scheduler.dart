import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../../navigation/incoming_intent.dart';
import '../../navigation/structured_destination_codec.dart';
import '../../navigation/destination.dart';

class LocalNotificationRequest {
  const LocalNotificationRequest({
    required this.id,
    required this.title,
    required this.body,
    required this.androidChannelId,
    required this.androidChannelName,
    this.destination,
  });

  final int id;
  final String title;
  final String body;
  final String androidChannelId;
  final String androidChannelName;
  final StructuredDestination? destination;
}

abstract interface class LocalNotificationScheduler {
  Future<void> initialize({
    required void Function(IncomingIntent intent) onIntent,
  });
  Future<void> show(LocalNotificationRequest request);
  Future<void> cancel(int id);
}

class FlutterLocalNotificationScheduler implements LocalNotificationScheduler {
  FlutterLocalNotificationScheduler({
    FlutterLocalNotificationsPlugin? plugin,
    this.androidDefaultIcon = 'ic_launcher',
    this.codec = const StructuredDestinationCodec(),
  }) : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;
  final String androidDefaultIcon;
  final StructuredDestinationCodec codec;

  @override
  Future<void> initialize({
    required void Function(IncomingIntent intent) onIntent,
  }) async {
    await _plugin.initialize(
      settings: InitializationSettings(
        android: AndroidInitializationSettings(androidDefaultIcon),
        iOS: const DarwinInitializationSettings(
          requestAlertPermission: false,
          requestBadgePermission: false,
          requestSoundPermission: false,
        ),
      ),
      onDidReceiveNotificationResponse: (response) {
        final destination = _decodeDestination(response.payload);
        if (destination == null) return;
        onIntent(
          IncomingIntent(
            source: IncomingIntentSource.notification,
            destination: destination,
          ),
        );
      },
    );
  }

  @override
  Future<void> show(LocalNotificationRequest request) {
    return _plugin.show(
      id: request.id,
      title: request.title,
      body: request.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          request.androidChannelId,
          request.androidChannelName,
        ),
        iOS: const DarwinNotificationDetails(),
      ),
      payload: request.destination == null
          ? null
          : codec.toJson(request.destination!),
    );
  }

  @override
  Future<void> cancel(int id) => _plugin.cancel(id: id);

  StructuredDestination? _decodeDestination(String? payload) {
    if (payload == null || payload.isEmpty) return null;
    return codec.fromJson(payload);
  }
}
