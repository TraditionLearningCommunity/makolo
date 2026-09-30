import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/background/background_coordinator.dart';
import 'package:makolo_mobile/background/workmanager_scheduler.dart';

void main() {
  test('workmanager payload decodes to the Makolo background contract', () {
    final task = decodeWorkmanagerTask(
      WorkmanagerBackgroundScheduler.taskName,
      {
        'task_id': 'upload-1',
        'kind': 'upload',
        'profile_id': 'profile-a',
        'operation_id': 'operation-1',
        'requires_network': true,
      },
    );

    expect(task?.id, 'upload-1');
    expect(task?.kind, BackgroundTaskKind.upload);
    expect(task?.profileId, 'profile-a');
    expect(task?.operationId, 'operation-1');
    expect(task?.requiresNetwork, isTrue);
  });

  test('workmanager round-trip preserves network-independent maintenance', () {
    final task = decodeWorkmanagerTask(
      WorkmanagerBackgroundScheduler.taskName,
      {
        'task_id': 'cache-1',
        'kind': 'cacheMaintenance',
        'profile_id': 'profile-a',
        'requires_network': false,
      },
    );

    expect(task?.kind, BackgroundTaskKind.cacheMaintenance);
    expect(task?.requiresNetwork, isFalse);
  });

  test('legacy workmanager payload remains conservatively network-bound', () {
    final task = decodeWorkmanagerTask(
      WorkmanagerBackgroundScheduler.taskName,
      {'task_id': 'legacy-1', 'kind': 'refresh', 'profile_id': 'profile-a'},
    );

    expect(task?.requiresNetwork, isTrue);
  });

  test('unknown workmanager task is rejected', () {
    expect(decodeWorkmanagerTask('other.task', {'task_id': 'x'}), isNull);
  });
}
