enum BackgroundTaskKind {
  flushOutbox,
  refresh,
  upload,
  download,
  cacheMaintenance,
}

class BackgroundTask {
  const BackgroundTask({
    required this.id,
    required this.kind,
    required this.profileId,
    this.operationId,
    this.requiresNetwork = true,
  });

  final String id;
  final BackgroundTaskKind kind;
  final String profileId;
  final String? operationId;
  final bool requiresNetwork;
}

typedef BackgroundTaskHandler = Future<bool> Function(BackgroundTask task);

class TaskRegistry {
  final Map<BackgroundTaskKind, BackgroundTaskHandler> _handlers = {};

  void register(BackgroundTaskKind kind, BackgroundTaskHandler handler) {
    _handlers[kind] = handler;
  }

  Future<bool> execute(BackgroundTask task) async {
    final handler = _handlers[task.kind];
    if (handler == null) return false;
    return handler(task);
  }
}

abstract interface class BackgroundScheduler {
  Future<void> schedule(BackgroundTask task);
  Future<void> cancel(String taskId);
}

class BackgroundCoordinator {
  const BackgroundCoordinator({
    required this.registry,
    required this.scheduler,
  });

  final TaskRegistry registry;
  final BackgroundScheduler scheduler;

  Future<bool> runNow(BackgroundTask task) => registry.execute(task);
  Future<void> schedule(BackgroundTask task) => scheduler.schedule(task);
  Future<void> cancel(String taskId) => scheduler.cancel(taskId);
}
