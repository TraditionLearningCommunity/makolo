enum EntryReason {
  normal,
  sessionExpired,
  accountSwitch,
  protectedIntent,
  protectedAction,
}

class SessionRecoveryController {
  String? _lastUsefulLocation;
  bool _recoverAfterAuthentication = false;
  EntryReason _entryReason = EntryReason.normal;

  void rememberLocation(String location) {
    if (location.isEmpty || location == '/') return;
    _lastUsefulLocation = location;
  }

  void markSessionExpired() {
    _recoverAfterAuthentication = true;
    _entryReason = EntryReason.sessionExpired;
  }

  void requireAuthenticationFor(String location) {
    rememberLocation(location);
    _recoverAfterAuthentication = true;
    _entryReason = EntryReason.protectedIntent;
  }

  void requireAuthentication(String location) {
    rememberLocation(location);
    _recoverAfterAuthentication = true;
    _entryReason = EntryReason.protectedAction;
  }

  void markAccountSwitch() {
    _lastUsefulLocation = null;
    _recoverAfterAuthentication = false;
    _entryReason = EntryReason.accountSwitch;
  }

  void markLoggedOut() {
    _lastUsefulLocation = null;
    _recoverAfterAuthentication = false;
    _entryReason = EntryReason.normal;
  }

  String initialLocation() {
    final destination = _recoverAfterAuthentication
        ? (_lastUsefulLocation ?? '/now')
        : '/now';
    _recoverAfterAuthentication = false;
    _entryReason = EntryReason.normal;
    return destination;
  }

  String? get lastUsefulLocation => _lastUsefulLocation;
  bool get awaitingAuthentication => _recoverAfterAuthentication;
  EntryReason get entryReason => _entryReason;
}
