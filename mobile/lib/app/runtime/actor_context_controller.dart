import 'package:flutter/foundation.dart';

import 'actor_context.dart';

abstract interface class ActorContextStore {
  Future<ActorContext> readActorContext(String profileId);
  Future<void> writeActorContext(String profileId, ActorContext context);
  Future<void> removeActorContext(String profileId);
}

final class ActorContextController extends ChangeNotifier {
  ActorContextController._({
    required this.profileId,
    required ActorContextStore store,
    required ActorContext initial,
  }) : _store = store,
       _value = initial;

  final String profileId;
  final ActorContextStore _store;
  ActorContext _value;

  ActorContext get value => _value;

  static Future<ActorContextController> restore({
    required String profileId,
    required ActorContextStore store,
  }) async {
    final initial = await store.readActorContext(profileId);
    return ActorContextController._(
      profileId: profileId,
      store: store,
      initial: initial,
    );
  }

  Future<void> selectPersonal() async {
    await _set(const PersonalActorContext());
  }

  Future<void> selectSpace(
    SpaceActorIdentity space, {
    ActorPerspective perspective = const ActorPerspective.all(),
  }) async {
    await _set(SpaceActorContext(space: space, perspective: perspective));
  }

  Future<void> selectPerspective(ActorPerspective perspective) async {
    final current = _value;
    if (current is! SpaceActorContext) {
      throw StateError('A perspective requires a Space actor context.');
    }
    await _set(current.copyWith(perspective: perspective));
  }

  Future<bool> revalidateSpaceContext(
    bool Function(SpaceActorIdentity space) isAvailable,
  ) async {
    final current = _value;
    if (current is! SpaceActorContext) return true;
    if (isAvailable(current.space)) return true;

    await selectPersonal();
    return false;
  }

  Future<void> forget() async {
    await _store.removeActorContext(profileId);
    if (_value is PersonalActorContext) return;
    _value = const PersonalActorContext();
    notifyListeners();
  }

  Future<void> _set(ActorContext next) async {
    if (_value == next) return;
    await _store.writeActorContext(profileId, next);
    _value = next;
    notifyListeners();
  }
}
