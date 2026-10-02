import 'dart:async';

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
    required this._store,
    required ActorContext initial,
  }) : _value = initial,
       _requestedValue = initial;

  final String profileId;
  final ActorContextStore _store;
  ActorContext _value;
  ActorContext _requestedValue;
  Future<void> _transitionTail = Future<void>.value();
  int _transitionRevision = 0;

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

  Future<void> selectPersonal() {
    return _set(const PersonalActorContext());
  }

  Future<void> selectSpace(
    SpaceActorIdentity space, {
    ActorPerspective perspective = const ActorPerspective.all(),
  }) {
    return _set(SpaceActorContext(space: space, perspective: perspective));
  }

  Future<void> selectPerspective(ActorPerspective perspective) {
    final current = _requestedValue;
    if (current is! SpaceActorContext) {
      throw StateError('A perspective requires a Space actor context.');
    }
    return _set(current.copyWith(perspective: perspective));
  }

  Future<bool> revalidateSpaceContext(
    FutureOr<bool> Function(SpaceActorIdentity space) isAvailable,
  ) async {
    final checked = _requestedValue;
    if (checked is! SpaceActorContext) return true;
    if (await isAvailable(checked.space)) return true;

    final latest = _requestedValue;
    if (latest is! SpaceActorContext || latest.space.id != checked.space.id) {
      return true;
    }

    await selectPersonal();
    return false;
  }

  Future<void> forget() {
    final next = const PersonalActorContext();
    _requestedValue = next;
    final revision = ++_transitionRevision;

    final operation = _transitionTail.then((_) async {
      if (revision != _transitionRevision) return;
      await _store.removeActorContext(profileId);
      if (revision != _transitionRevision || _value == next) return;
      _value = next;
      notifyListeners();
    });
    _continueAfter(operation);
    return operation;
  }

  Future<void> _set(ActorContext next) {
    if (_requestedValue == next && _value == next) {
      return Future<void>.value();
    }

    _requestedValue = next;
    final revision = ++_transitionRevision;
    final operation = _transitionTail.then((_) async {
      if (revision != _transitionRevision) return;
      await _store.writeActorContext(profileId, next);
      if (revision != _transitionRevision || _value == next) return;
      _value = next;
      notifyListeners();
    });
    _continueAfter(operation);
    return operation;
  }

  void _continueAfter(Future<void> operation) {
    _transitionTail = operation.then<void>(
      (_) {},
      onError: (Object _, StackTrace __) {},
    );
  }
}
