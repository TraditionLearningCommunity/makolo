import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';

void main() {
  late Directory directory;
  late File file;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp(
      'makolo-launch-preferences-stabilization-',
    );
    file = File('${directory.path}/preferences.json');
  });

  tearDown(() async {
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  });

  test('concurrent actor and shell writes preserve both values', () async {
    final store = FileLaunchPreferencesStore.forFile(file);
    final space = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-a', slug: 'space-a'),
      perspective: ActorPerspective.opaque('finance'),
    );

    await Future.wait<void>([
      store.writeActorContext('profile-a', space),
      store.writeShellLocation('profile-a', '/space/work'),
    ]);

    final reopened = FileLaunchPreferencesStore.forFile(file);
    expect(await reopened.readActorContext('profile-a'), space);
    expect(await reopened.readShellLocation('profile-a'), '/space/work');
  });

  test('concurrent stores cannot lose another Profile actor preference', () async {
    final storeA = FileLaunchPreferencesStore.forFile(file);
    final storeB = FileLaunchPreferencesStore.forFile(file);
    final actorA = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-a', slug: 'space-a'),
      perspective: ActorPerspective.opaque('finance'),
    );
    final actorB = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-b', slug: 'space-b'),
    );

    await Future.wait<void>([
      storeA.writeActorContext('profile-a', actorA),
      storeB.writeActorContext('profile-b', actorB),
    ]);

    final reopened = FileLaunchPreferencesStore.forFile(file);
    expect(await reopened.readActorContext('profile-a'), actorA);
    expect(await reopened.readActorContext('profile-b'), actorB);
  });
}
