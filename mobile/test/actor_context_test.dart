import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';

void main() {
  late Directory directory;
  late File file;
  late FileLaunchPreferencesStore store;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp(
      'makolo-actor-context-test-',
    );
    file = File('${directory.path}/preferences.json');
    store = FileLaunchPreferencesStore.forFile(file);
  });

  tearDown(() async {
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  });

  test('personal actor context is the safe default', () async {
    final controller = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    addTearDown(controller.dispose);

    expect(controller.value, const PersonalActorContext());
    expect(controller.value.kind, ActorContextKind.personal);
  });

  test('Space actor identity and perspectives remain distinguishable', () {
    final spaceA = SpaceActorIdentity(id: 'space-a', slug: 'space-a');
    final spaceB = SpaceActorIdentity(id: 'space-b', slug: 'space-b');

    final allA = SpaceActorContext(space: spaceA);
    final financeA = SpaceActorContext(
      space: spaceA,
      perspective: ActorPerspective.opaque('perspective:finance'),
    );
    final allB = SpaceActorContext(space: spaceB);

    expect(allA, isNot(financeA));
    expect(allA, isNot(allB));
    expect(financeA.space, spaceA);
    expect(financeA.perspective.id, 'perspective:finance');
  });

  test('personal context persists across store reopen', () async {
    final controller = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    await controller.selectPersonal();
    controller.dispose();

    final reopened = FileLaunchPreferencesStore.forFile(file);
    expect(
      await reopened.readActorContext('profile-a'),
      const PersonalActorContext(),
    );
  });

  test('Space context and perspective persist across store reopen', () async {
    final controller = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');

    await controller.selectSpace(space);
    await controller.selectPerspective(
      ActorPerspective.opaque('perspective:finance'),
    );
    controller.dispose();

    final reopened = FileLaunchPreferencesStore.forFile(file);
    expect(
      await reopened.readActorContext('profile-a'),
      SpaceActorContext(
        space: space,
        perspective: ActorPerspective.opaque('perspective:finance'),
      ),
    );
  });

  test('actor context is isolated per Profile', () async {
    final profileA = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    final profileB = await ActorContextController.restore(
      profileId: 'profile-b',
      store: store,
    );
    addTearDown(profileA.dispose);
    addTearDown(profileB.dispose);

    final spaceX = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    final spaceY = SpaceActorIdentity(id: 'space-y', slug: 'space-y');

    await profileA.selectSpace(spaceX);
    await profileB.selectSpace(
      spaceY,
      perspective: ActorPerspective.opaque('perspective-y'),
    );

    expect(
      await store.readActorContext('profile-a'),
      SpaceActorContext(space: spaceX),
    );
    expect(
      await store.readActorContext('profile-b'),
      SpaceActorContext(
        space: spaceY,
        perspective: ActorPerspective.opaque('perspective-y'),
      ),
    );

    final restoredA = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    addTearDown(restoredA.dispose);
    expect(restoredA.value, SpaceActorContext(space: spaceX));
  });

  test('personal to Space to personal produces explicit states', () async {
    final controller = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    addTearDown(controller.dispose);
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');

    expect(controller.value, const PersonalActorContext());

    await controller.selectSpace(space);
    expect(controller.value, SpaceActorContext(space: space));

    await controller.selectPersonal();
    expect(controller.value, const PersonalActorContext());
  });

  test(
    'invalid or legacy stored values fall back to personal without crash',
    () async {
      await file.writeAsString(
        jsonEncode({
          'has_completed_onboarding': true,
          'actor_contexts': {
            'profile-a': {
              'version': 99,
              'kind': 'space',
              'space': {'id': 'space-x', 'slug': 'space-x'},
            },
            'profile-b': 'corrupt',
          },
        }),
      );

      expect(
        await store.readActorContext('profile-a'),
        const PersonalActorContext(),
      );
      expect(
        await store.readActorContext('profile-b'),
        const PersonalActorContext(),
      );
      expect(
        await store.readActorContext('profile-legacy'),
        const PersonalActorContext(),
      );
    },
  );

  test(
    'revalidation falls back to personal instead of another Space',
    () async {
      final controller = await ActorContextController.restore(
        profileId: 'profile-a',
        store: store,
      );
      addTearDown(controller.dispose);
      final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');

      await controller.selectSpace(space);

      final stillValid = await controller.revalidateSpaceContext(
        (candidate) => candidate.id == 'another-space',
      );

      expect(stillValid, isFalse);
      expect(controller.value, const PersonalActorContext());
      expect(
        await store.readActorContext('profile-a'),
        const PersonalActorContext(),
      );
    },
  );

  test(
    'removing a Profile actor preference does not affect another Profile',
    () async {
      final spaceX = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
      final spaceY = SpaceActorIdentity(id: 'space-y', slug: 'space-y');
      await store.writeActorContext(
        'profile-a',
        SpaceActorContext(space: spaceX),
      );
      await store.writeActorContext(
        'profile-b',
        SpaceActorContext(space: spaceY),
      );

      await store.removeActorContext('profile-a');

      expect(
        await store.readActorContext('profile-a'),
        const PersonalActorContext(),
      );
      expect(
        await store.readActorContext('profile-b'),
        SpaceActorContext(space: spaceY),
      );
    },
  );

  test('serialized actor context contains no authority state', () async {
    final space = SpaceActorIdentity(id: 'space-x', slug: 'space-x');
    await store.writeActorContext(
      'profile-a',
      SpaceActorContext(
        space: space,
        perspective: ActorPerspective.opaque('opaque-perspective'),
      ),
    );

    final raw = await file.readAsString();

    expect(raw, contains('"kind":"space"'));
    expect(raw, contains('"space"'));
    expect(raw, contains('"perspective"'));
    expect(raw, isNot(contains('permission')));
    expect(raw, isNot(contains('mandate')));
    expect(raw, isNot(contains('token')));
    expect(raw, isNot(contains('canManage')));
  });
}
