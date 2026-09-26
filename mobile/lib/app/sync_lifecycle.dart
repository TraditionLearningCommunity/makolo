import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:drift/drift.dart';
import 'package:flutter/widgets.dart';

import '../network/api_error.dart';
import '../sync/outbox/outbox_repository.dart';
import '../sync/sync_status.dart';
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
  StreamSubscription<OutboxSummary>? _outbox;
  bool _online = true;
  bool _syncing = false;
  bool _syncFailed = false;
  OutboxSummary _outboxSummary = OutboxSummary.empty;
  DateTime? _lastUpdatedAt;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_initConnectivity());
    _bindOutbox();
    unawaited(_refresh());
    _connectivity = Connectivity().onConnectivityChanged.listen((results) {
      final online = results.any((result) => result != ConnectivityResult.none);
      if (mounted) setState(() => _online = online);
      if (online) unawaited(_refresh());
    });
  }

  Future<void> _initConnectivity() async {
    final results = await Connectivity().checkConnectivity();
    if (!mounted) return;
    setState(
      () => _online = results.any(
        (result) => result != ConnectivityResult.none,
      ),
    );
  }

  void _bindOutbox() {
    unawaited(_outbox?.cancel());
    _outbox = widget.runtime.outbox?.watchSummary().listen((summary) {
      if (mounted) setState(() => _outboxSummary = summary);
    });
  }

  @override
  void didUpdateWidget(covariant SyncLifecycle oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.session?.profileId !=
        widget.runtime.session?.profileId) {
      _bindOutbox();
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
    final database = widget.runtime.database;
    if (sync == null || database == null || _syncing) return;
    if (mounted) {
      setState(() {
        _syncing = true;
        _syncFailed = false;
      });
    }
    try {
      await sync.refreshRoots();
      final failedSources =
          await (database.select(database.syncSources)
                ..where((row) => row.invalidated.equals(true)))
              .get();
      if (mounted) {
        setState(() {
          _syncFailed = failedSources.isNotEmpty;
          if (!_syncFailed) _lastUpdatedAt = DateTime.now();
        });
      }
    } on MakoloApiError catch (error) {
      if (error.statusCode == 401) {
        widget.onSessionExpired();
      } else if (mounted) {
        setState(() => _syncFailed = true);
      }
    } on Object {
      if (mounted) setState(() => _syncFailed = true);
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  SyncStatus get _status {
    if (_outboxSummary.conflictCount > 0) {
      return SyncStatus(
        state: SyncVisualState.conflict,
        pendingCount: _outboxSummary.pendingCount,
        lastUpdatedAt: _lastUpdatedAt,
      );
    }
    if (!_online) {
      return SyncStatus(
        state: SyncVisualState.offline,
        pendingCount: _outboxSummary.pendingCount,
        lastUpdatedAt: _lastUpdatedAt,
      );
    }
    if (_syncFailed || _outboxSummary.failedCount > 0) {
      return SyncStatus(
        state: SyncVisualState.failed,
        pendingCount: _outboxSummary.pendingCount,
        lastUpdatedAt: _lastUpdatedAt,
      );
    }
    if (_syncing) {
      return SyncStatus(
        state: SyncVisualState.syncing,
        pendingCount: _outboxSummary.pendingCount,
        lastUpdatedAt: _lastUpdatedAt,
      );
    }
    if (_outboxSummary.pendingCount > 0) {
      return SyncStatus(
        state: SyncVisualState.pending,
        pendingCount: _outboxSummary.pendingCount,
        lastUpdatedAt: _lastUpdatedAt,
      );
    }
    return SyncStatus(
      state: SyncVisualState.synced,
      lastUpdatedAt: _lastUpdatedAt,
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_connectivity?.cancel());
    unawaited(_outbox?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      SyncStatusScope(status: _status, child: widget.child);
}
