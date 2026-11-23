import 'dart:async';

/// Serializes access to the database files owned by successive app runtimes.
///
/// Does not decide the active Profile or manage business permissions. A new
/// runtime can open its files only after the previous one finishes closing.
class RuntimeCloseBarrier {
  Future<void> _previousClosed = Future<void>.value();

  Future<T> open<T>(Future<T> Function() create) async {
    await _previousClosed;
    return create();
  }

  void release<T>(Future<T> pending, Future<void> Function(T) close) {
    _previousClosed = pending.then<void>(
      (resource) => close(resource),
      onError: (Object _, StackTrace _) {
        // Failed initialization returned no successfully built resource.
      },
    );
    // Observe an eventual close failure even if there is no replacement. The
    // original future still carries the failure to the next open().
    unawaited(_previousClosed.catchError((Object _, StackTrace _) {}));
  }
}
