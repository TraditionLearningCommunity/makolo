import 'package:home_widget/home_widget.dart';

class AmbientSnapshot {
  const AmbientSnapshot({
    required this.kind,
    required this.title,
    required this.status,
    required this.updatedAt,
    this.subtitle,
    this.timeLabel,
    this.placeLabel,
    this.deepLink,
  });

  final String kind;
  final String title;
  final String? subtitle;
  final String status;
  final String? timeLabel;
  final String? placeLabel;
  final String? deepLink;
  final DateTime updatedAt;

  Map<String, String?> toMap() => {
    'kind': kind,
    'title': title,
    'subtitle': subtitle,
    'status': status,
    'time': timeLabel,
    'place': placeLabel,
    'deep_link': deepLink,
    'updated_at': updatedAt.toUtc().toIso8601String(),
  };
}

abstract interface class AmbientSnapshotPublisher {
  Future<void> publish(AmbientSnapshot snapshot);
  Future<void> clear();
}

class HomeWidgetAmbientPublisher implements AmbientSnapshotPublisher {
  const HomeWidgetAmbientPublisher({
    required this.widgetName,
    this.iosWidgetName,
    this.appGroupId,
  });

  final String widgetName;
  final String? iosWidgetName;
  final String? appGroupId;

  @override
  Future<void> publish(AmbientSnapshot snapshot) async {
    for (final entry in snapshot.toMap().entries) {
      await HomeWidget.saveWidgetData<String>(
        'makolo.${entry.key}',
        entry.value,
        appGroupId: appGroupId,
      );
    }
    await HomeWidget.updateWidget(name: widgetName, iOSName: iosWidgetName);
  }

  @override
  Future<void> clear() async {
    const keys = {
      'kind',
      'title',
      'subtitle',
      'status',
      'time',
      'place',
      'deep_link',
      'updated_at',
    };
    for (final key in keys) {
      await HomeWidget.saveWidgetData<String>(
        'makolo.$key',
        null,
        appGroupId: appGroupId,
      );
    }
    await HomeWidget.updateWidget(name: widgetName, iOSName: iosWidgetName);
  }
}
