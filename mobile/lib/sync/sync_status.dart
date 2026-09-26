import 'package:flutter/widgets.dart';

enum SyncVisualState {
  synced,
  syncing,
  pending,
  offline,
  conflict,
  failed,
  stale,
}

class SyncStatus {
  const SyncStatus({
    required this.state,
    this.pendingCount = 0,
    this.lastUpdatedAt,
  });

  final SyncVisualState state;
  final int pendingCount;
  final DateTime? lastUpdatedAt;

  bool get isDegraded =>
      state == SyncVisualState.offline ||
      state == SyncVisualState.conflict ||
      state == SyncVisualState.failed ||
      state == SyncVisualState.stale;
}

class SyncStatusScope extends InheritedWidget {
  const SyncStatusScope({
    super.key,
    required this.status,
    required super.child,
  });

  final SyncStatus status;

  static SyncStatus? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<SyncStatusScope>()
        ?.status;
  }

  @override
  bool updateShouldNotify(SyncStatusScope oldWidget) =>
      oldWidget.status.state != status.state ||
      oldWidget.status.pendingCount != status.pendingCount ||
      oldWidget.status.lastUpdatedAt != status.lastUpdatedAt;
}
