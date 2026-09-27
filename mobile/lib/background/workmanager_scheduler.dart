import 'package:workmanager/workmanager.dart';

import 'background_coordinator.dart';

class WorkmanagerBackgroundScheduler implements BackgroundScheduler {
  WorkmanagerBackgroundScheduler({Workmanager? workmanager})
    : _workmanager = workmanager ?? Workmanager();

  final Workmanager _workmanager;

  static const taskName = 'makolo.background';

  @override
  Future<void> schedule(BackgroundTask task) {
    return _workmanager.registerOneOffTask(
      task.id,
      taskName,
      inputData: {
        'task_id': task.id,
        'kind': task.kind.name,
        'profile_id': task.profileId,
        if (task.operationId != null) 'operation_id': task.operationId,
      },
      constraints: Constraints(
        networkType: task.requiresNetwork
            ? NetworkType.connected
            : NetworkType.notRequired,
      ),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
  }

  @override
  Future<void> cancel(String taskId) {
    return _workmanager.cancelByUniqueName(taskId);
  }
}

BackgroundTask? decodeWorkmanagerTask(
  String taskName,
  Map<String, dynamic>? inputData,
) {
  if (taskName != WorkmanagerBackgroundScheduler.taskName ||
      inputData == null) {
    return null;
  }
  final id = inputData['task_id']?.toString();
  final profileId = inputData['profile_id']?.toString();
  final kindName = inputData['kind']?.toString();
  if (id == null || profileId == null || kindName == null) return null;

  BackgroundTaskKind? kind;
  for (final candidate in BackgroundTaskKind.values) {
    if (candidate.name == kindName) {
      kind = candidate;
      break;
    }
  }
  if (kind == null) return null;

  return BackgroundTask(
    id: id,
    kind: kind,
    profileId: profileId,
    operationId: inputData['operation_id']?.toString(),
  );
}
