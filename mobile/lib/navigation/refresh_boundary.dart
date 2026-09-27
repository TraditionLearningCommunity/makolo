import 'package:flutter/material.dart';

import '../app/sync_lifecycle.dart';

class MakoloRefreshBoundary extends StatelessWidget {
  const MakoloRefreshBoundary({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ScrollConfiguration(
      behavior: const _MakoloRefreshScrollBehavior(),
      child: RefreshIndicator(
        notificationPredicate: (notification) =>
            notification.metrics.axis == Axis.vertical,
        onRefresh: () async {
          final scope = SyncRefreshScope.maybeOf(context);
          if (scope != null) await scope.refresh();
        },
        child: child,
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
