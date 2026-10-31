import 'dart:async';

/// Lightweight reusable scheduler for a user's current search intent.
///
/// Calling [changed] invalidates any response from an earlier request,
/// resets pending typing, and schedules exactly one new request. A source
/// may additionally cancel its HTTP request when supported.
class ProgressiveSearchCoordinator {
  ProgressiveSearchCoordinator({
    required this.onSearch,
    this.debounce = const Duration(milliseconds: 350),
  });

  final Future<void> Function(int revision) onSearch;
  final Duration debounce;
  Timer? _timer;
  int _revision = 0;
  bool _disposed = false;

  int get revision => _revision;

  bool isCurrent(int revision) => !_disposed && revision == _revision;

  void invalidate() {
    if (_disposed) return;
    _revision++;
    _timer?.cancel();
    _timer = null;
  }

  void changed({bool immediate = false}) {
    if (_disposed) return;
    final revision = ++_revision;
    _timer?.cancel();
    _timer = null;
    if (immediate) {
      unawaited(onSearch(revision));
    } else {
      _timer = Timer(debounce, () {
        _timer = null;
        if (isCurrent(revision)) unawaited(onSearch(revision));
      });
    }
  }

  Future<void> refresh() async {
    if (_disposed) return;
    final revision = ++_revision;
    _timer?.cancel();
    _timer = null;
    await onSearch(revision);
  }

  void dispose() {
    _disposed = true;
    _revision++;
    _timer?.cancel();
    _timer = null;
  }
}
