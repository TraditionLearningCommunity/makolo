import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';

class _DelayedActorStore implements ActorContextStore {
  _DelayedActorStore({this.delayFirstWrite = false});

  final bool delayFirstWrite;
  final Map<String, ActorContext> values = <String, ActorContext>{};
  final Completer<void> firstWriteStarted = Completer<void>();
  final Completer<void> releaseFirstWrite = Completer<void>();
  int _writeCount = 0;

  @override
  Future<ActorContext> readActorContext(String profileId) async =>
      values[profileId] ?? const PersonalActorContext();

  @override
  Future<void> writeActorContext(String profileId, ActorContext context) async {
    _writeCount += 1;
    if (delayFirstWrite && _writeCount == 1) {
      if (!firstWriteStarted.isCompleted) {
        firstWriteStarted.complete();
      }
      await releaseFirstWrite.future;
    }
    values[profileId] = context;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    values.remove(profileId);
  }
}

void main() {
  test(
    'later actor selection wins when an earlier persistence finishes late',
    () async {
      final store = _DelayedActorStore(delayFirstWrite: true);
      final controller = await ActorContextController.restore(
        profileId: 'profile-a',
        store: store,
      );
      addTearDown(controller.dispose);

      final spaceA = SpaceActorIdentity(id: 'space-a', slug: 'space-a');
      final spaceB = SpaceActorIdentity(id: 'space-b', slug: 'space-b');

      final selectA = controller.selectSpace(spaceA);
      await store.firstWriteStarted.future;

      final selectB = controller.selectSpace(spaceB);
      store.releaseFirstWrite.complete();

      await Future.wait<void>([selectA, selectB]);

      expect(controller.value, SpaceActorContext(space: spaceB));
      expect(store.values['profile-a'], SpaceActorContext(space: spaceB));
    },
  );

  test(
    'returning to the committed actor rewrites persistence after a stale write',
    () async {
      final store = _DelayedActorStore(delayFirstWrite: true);
      final controller = await ActorContextController.restore(
        profileId: 'profile-a',
        store: store,
      );
      addTearDown(controller.dispose);

      final spaceA = SpaceActorIdentity(id: 'space-a', slug: 'space-a');

      final selectA = controller.selectSpace(spaceA);
      await store.firstWriteStarted.future;

      final selectPersonal = controller.selectPersonal();
      store.releaseFirstWrite.complete();

      await Future.wait<void>([selectA, selectPersonal]);

      expect(controller.value, const PersonalActorContext());
      expect(store.values['profile-a'], const PersonalActorContext());
    },
  );

  test(
    'late revocation result for Space A cannot revoke a newer Space B',
    () async {
      final store = _DelayedActorStore();
      final controller = await ActorContextController.restore(
        profileId: 'profile-a',
        store: store,
      );
      addTearDown(controller.dispose);

      final spaceA = SpaceActorIdentity(id: 'space-a', slug: 'space-a');
      final spaceB = SpaceActorIdentity(id: 'space-b', slug: 'space-b');
      await controller.selectSpace(spaceA);

      final validationStarted = Completer<void>();
      final authoritativeResult = Completer<bool>();
      final validation = controller.revalidateSpaceContext((space) {
        expect(space.id, 'space-a');
        validationStarted.complete();
        return authoritativeResult.future;
      });

      await validationStarted.future;
      await controller.selectSpace(spaceB);
      authoritativeResult.complete(false);

      expect(await validation, isTrue);
      expect(controller.value, SpaceActorContext(space: spaceB));
      expect(store.values['profile-a'], SpaceActorContext(space: spaceB));
    },
  );

  test('revocation still falls back to Personal when the same Space remains active', () async {
    final store = _DelayedActorStore();
    final controller = await ActorContextController.restore(
      profileId: 'profile-a',
      store: store,
    );
    addTearDown(controller.dispose);

    final space = SpaceActorIdentity(id: 'space-a', slug: 'old-slug');
    await controller.selectSpace(space);

    final validationStarted = Completer<void>();
    final authoritativeResult = Completer<bool>();
    final validation = controller.revalidateSpaceContext((candidate) {
      expect(candidate.id, 'space-a');
      validationStarted.complete();
      return authoritativeResult.future;
    });

    await validationStarted.future;
    await controller.selectSpace(
      SpaceActorIdentity(id: 'space-a', slug: 'new-slug'),
      perspective: ActorPerspective.opaque('finance'),
    );
    authoritativeResult.complete(false);

    expect(await validation, isFalse);
    expect(controller.value, const PersonalActorContext());
    expect(store.values['profile-a'], const PersonalActorContext());
  });
}
