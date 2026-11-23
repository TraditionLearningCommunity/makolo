import 'package:flutter/material.dart';

/// Observes a finite, server-paginated list without changing server paging.
///
/// This widget does not create new data or infer that more results exist.
class LoadMoreOnScroll extends StatelessWidget {
  const LoadMoreOnScroll({
    super.key,
    required this.child,
    required this.hasMore,
    required this.loading,
    required this.loadMore,
  });

  final Widget child;
  final bool hasMore;
  final bool loading;
  final VoidCallback loadMore;

  @override
  Widget build(BuildContext context) {
    return NotificationListener<ScrollNotification>(
      onNotification: (notification) {
        if (notification.depth == 0 &&
            hasMore &&
            !loading &&
            notification.metrics.extentAfter < 420 &&
            notification is ScrollUpdateNotification) {
          loadMore();
        }
        return false;
      },
      child: child,
    );
  }
}
