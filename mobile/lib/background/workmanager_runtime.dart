import 'package:workmanager/workmanager.dart';

typedef WorkmanagerDispatcher = void Function();

class WorkmanagerRuntime {
  WorkmanagerRuntime({Workmanager? workmanager})
    : _workmanager = workmanager ?? Workmanager();

  final Workmanager _workmanager;
  bool _initialized = false;

  bool get initialized => _initialized;

  Future<void> initialize(WorkmanagerDispatcher dispatcher) async {
    if (_initialized) return;
    await _workmanager.initialize(dispatcher);
    _initialized = true;
  }
}

/// Workmanager is opportunistic/deferred execution. It is not an exact
/// business scheduler; server/owner state remains authoritative.
@pragma('vm:entry-point')
void makoloBackgroundDispatcher() {
  Workmanager().executeTask((taskName, inputData) async {
    // PAR-1C intentionally keeps the OS isolate bounded. Profile-scoped
    // database/sync work is resumed through the foreground owner runtime until
    // an identity-safe background composition root is available.
    return true;
  });
}
