import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/background/background_coordinator.dart';

class MemoryScheduler implements BackgroundScheduler {
  final scheduled = <BackgroundTask>[];
  final cancelled = <String>[];

  @override
  Future<void> schedule(BackgroundTask task) async => scheduled.add(task);

  @override
  Future<void> cancel(String taskId) async => cancelled.add(taskId);
}

void main() {
  test('background registry executes only registered work', () async {
    final registry = TaskRegistry()
      ..register(
        BackgroundTaskKind.flushOutbox,
        (task) async => task.profileId == 'profile-a',
      );
    const known = BackgroundTask(
      id: 'flush-a',
      kind: BackgroundTaskKind.flushOutbox,
      profileId: 'profile-a',
    );
    const unknown = BackgroundTask(
      id: 'upload-a',
      kind: BackgroundTaskKind.upload,
      profileId: 'profile-a',
    );

    expect(await registry.execute(known), isTrue);
    expect(await registry.execute(unknown), isFalse);
  });

  test('coordinator delegates OS scheduling without claiming execution', () async {
    final scheduler = MemoryScheduler();
    final coordinator = BackgroundCoordinator(
      registry: TaskRegistry(),
      scheduler: scheduler,
    );
    const task = BackgroundTask(
      id: 'refresh-a',
      kind: BackgroundTaskKind.refresh,
      profileId: 'profile-a',
    );

    await coordinator.schedule(task);
    expect(scheduler.scheduled.single, same(task));
  });
}
