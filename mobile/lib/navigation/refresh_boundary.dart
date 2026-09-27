import 'dart:async';

import 'package:flutter/material.dart';

import '../app/sync_lifecycle.dart';

class MakoloRefreshBoundary extends StatefulWidget {
  const MakoloRefreshBoundary({super.key, required this.child});

  final Widget child;

  @override
  State<MakoloRefreshBoundary> createState() => _MakoloRefreshBoundaryState();
}

class _MakoloRefreshBoundaryState extends State<MakoloRefreshBoundary> {
  static const double _triggerExtent = 64;
  double _pullExtent = 0;
  bool _refreshing = false;

  bool _onScroll(ScrollNotification notification) {
    if (notification is ScrollStartNotification &&
        notification.dragDetails != null) {
      _setPullExtent(0);
      return false;
    }

    if (notification is OverscrollNotification &&
        notification.dragDetails != null &&
        notification.metrics.axis == Axis.vertical &&
        notification.metrics.pixels <= notification.metrics.minScrollExtent &&
        notification.overscroll < 0) {
      _setPullExtent(_pullExtent + notification.overscroll.abs());
      return false;
    }

    if (notification is ScrollEndNotification && _pullExtent > 0) {
      final shouldRefresh = _pullExtent >= _triggerExtent;
      _setPullExtent(0);
      if (shouldRefresh) {
        unawaited(_runRefresh());
      }
    }
    return false;
  }

  void _setPullExtent(double value) {
    if (!mounted || _pullExtent == value) return;
    setState(() => _pullExtent = value);
  }

  Future<void> _runRefresh() async {
    if (_refreshing) return;
    final scope = SyncRefreshScope.maybeOf(context);
    if (scope == null) return;

    setState(() => _refreshing = true);
    try {
      await scope.refresh();
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = (_pullExtent / _triggerExtent).clamp(0.0, 1.0).toDouble();
    return ScrollConfiguration(
      behavior: const _MakoloRefreshScrollBehavior(),
      child: NotificationListener<ScrollNotification>(
        onNotification: _onScroll,
        child: Stack(
          children: [
            Positioned.fill(child: widget.child),
            if (_refreshing || _pullExtent > 0)
              Positioned(
                top: 8,
                left: 0,
                right: 0,
                child: IgnorePointer(
                  child: Center(
                    child: Semantics(
                      liveRegion: _refreshing,
                      label: _refreshing
                          ? 'Mise à jour…'
                          : 'Tirez pour mettre à jour',
                      child: SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          value: _refreshing ? null : progress,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _MakoloRefreshScrollBehavior extends MaterialScrollBehavior {
  const _MakoloRefreshScrollBehavior();

  @override
  ScrollPhysics getScrollPhysics(BuildContext context) {
    return const AlwaysScrollableScrollPhysics().applyTo(
      super.getScrollPhysics(context),
    );
  }
}
