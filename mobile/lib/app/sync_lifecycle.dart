import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';

import 'providers.dart';

class SyncLifecycle extends StatefulWidget {
  const SyncLifecycle({
    super.key,
    required this.runtime,
    required this.child,
  });

  final AppRuntime runtime;
  final Widget child;

  @override
  State<SyncLifecycle> createState() => _SyncLifecycleState();
}

class _SyncLifecycleState extends State<SyncLifecycle>
    with WidgetsBindingObserver {
  StreamSubscription<List<ConnectivityResult>>? _connectivity;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _connectivity = Connectivity().onConnectivityChanged.listen((results) {
      if (results.any((result) => result != ConnectivityResult.none)) {
        unawaited(widget.runtime.sync?.refreshRoots());
      }
    });
  }

  @override
  void didUpdateWidget(covariant SyncLifecycle oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.session?.profileId !=
        widget.runtime.session?.profileId) {
      unawaited(widget.runtime.sync?.refreshRoots());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(widget.runtime.sync?.refreshRoots());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_connectivity?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
