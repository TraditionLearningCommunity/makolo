import 'dart:convert';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

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
    required void Function(StructuredDestination destination) onDestination,
  });
  Future<void> show(LocalNotificationRequest request);
  Future<void> cancel(int id);
}

class FlutterLocalNotificationScheduler implements LocalNotificationScheduler {
  FlutterLocalNotificationScheduler({
    FlutterLocalNotificationsPlugin? plugin,
    this.androidDefaultIcon = 'ic_launcher',
  }) : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;
  final String androidDefaultIcon;

  @override
  Future<void> initialize({
    required void Function(StructuredDestination destination) onDestination,
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
        if (destination != null) onDestination(destination);
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
          : jsonEncode({
              'kind': request.destination!.kind,
              'id': request.destination!.id,
            }),
    );
  }

  @override
  Future<void> cancel(int id) => _plugin.cancel(id: id);

  StructuredDestination? _decodeDestination(String? payload) {
    if (payload == null || payload.isEmpty) return null;
    try {
      final value = jsonDecode(payload);
      if (value is! Map<String, dynamic>) return null;
      final kind = value['kind']?.toString();
      final id = value['id']?.toString();
      if (kind == null || id == null || kind.isEmpty || id.isEmpty) {
        return null;
      }
      return StructuredDestination(kind: kind, id: id);
    } on FormatException {
      return null;
    }
  }
}
