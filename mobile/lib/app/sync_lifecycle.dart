import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';

import '../network/api_error.dart';
import 'providers.dart';

class SyncLifecycle extends StatefulWidget {
  const SyncLifecycle({
    super.key,
    required this.runtime,
    required this.child,
    required this.onSessionExpired,
  });

  final AppRuntime runtime;
  final Widget child;
  final VoidCallback onSessionExpired;

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
    unawaited(_refresh());
    _connectivity = Connectivity().onConnectivityChanged.listen((results) {
      if (results.any((result) => result != ConnectivityResult.none)) {
        unawaited(_refresh());
      }
    });
  }

  @override
  void didUpdateWidget(covariant SyncLifecycle oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.session?.profileId !=
        widget.runtime.session?.profileId) {
      unawaited(_refresh());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_refresh());
    }
  }

  Future<void> _refresh() async {
    final sync = widget.runtime.sync;
    if (sync == null) return;
    try {
      await sync.refreshRoots();
    } on MakoloApiError catch (error) {
      if (error.statusCode == 401) {
        widget.onSessionExpired();
      }
    } on Object {
      // The local store remains available. Per-source failures are persisted by
      // SyncEngine and a later lifecycle/network trigger will retry.
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
