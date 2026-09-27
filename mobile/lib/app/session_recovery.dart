class SessionRecoveryController {
  String? _lastUsefulLocation;
  bool _recoverAfterAuthentication = false;

  void rememberLocation(String location) {
    if (location.isEmpty || location == '/') return;
    _lastUsefulLocation = location;
  }

  void markSessionExpired() {
    _recoverAfterAuthentication = true;
  }

  String initialLocation() {
    if (!_recoverAfterAuthentication) return '/now';
    _recoverAfterAuthentication = false;
    return _lastUsefulLocation ?? '/now';
  }

  String? get lastUsefulLocation => _lastUsefulLocation;
  bool get awaitingAuthentication => _recoverAfterAuthentication;
}
