import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';

import '../data/files/media_cache.dart';
import '../data/files/profile_file_store.dart';
import '../data/files/profile_recognition_image_store.dart';
import '../features/access/access_credential_vault.dart';
import '../features/journey/journey_repository.dart';
import '../network/api_error.dart';
import '../sync/outbox/outbox_repository.dart';
import '../sync/sync_status.dart';
import 'providers.dart';
import 'runtime/actor_context.dart';

class SyncRefreshScope extends InheritedWidget {
  const SyncRefreshScope({
    super.key,
    required this.refresh,
    required super.child,
  });

  final Future<void> Function() refresh;

  static SyncRefreshScope? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<SyncRefreshScope>();

  @override
  bool updateShouldNotify(SyncRefreshScope oldWidget) => false;
}

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
  Timer? _outboxRetryTimer;
  int _retryRevision = 0;
  bool _online = true;
  bool _syncing = false;
  bool _refreshQueued = false;
  bool _syncFailed = false;
  OutboxSummary _outboxSummary = OutboxSummary.empty;
  DateTime? _lastUpdatedAt;
  DateTime? _lastStorageMaintenanceAt;
  String? _maintainedProfile;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.runtime.actorContext?.addListener(_onActorChanged);
    unawaited(_initConnectivity());
    _bindOutbox();
    unawaited(_refresh());
    _connectivity = Connectivity().onConnectivityChanged.listen((results) {
      final online = results.any((result) => result != ConnectivityResult.none);
      final restored = online && !_online;
      if (mounted) setState(() => _online = online);
      if (!online) {
        _outboxRetryTimer?.cancel();
        _retryRevision++;
      }
      if (restored) {
        widget.runtime.sync?.onConnectivityRestored();
        unawaited(_armOutboxRetry(widget.runtime));
        unawaited(_refresh());
      }
    });
  }

  Future<void> _initConnectivity() async {
    final results = await Connectivity().checkConnectivity();
    if (!mounted) return;
    setState(
      () =>
          _online = results.any((result) => result != ConnectivityResult.none),
    );
  }

  void _onActorChanged() {
    // A changed Profile/Space perspective is an acquisition trigger, not an
    // authority grant. Owner-scoped refresh still validates the actor.
    unawaited(_refresh());
  }

  void _bindOutbox() {
    unawaited(_outbox?.cancel());
    _outbox = widget.runtime.outbox?.watchSummary().listen((summary) {
      if (mounted) {
        setState(() => _outboxSummary = summary);
        unawaited(_armOutboxRetry(widget.runtime));
      }
    });
  }

  /// Retry timing belongs to the existing foreground lifecycle, not to
  /// widgets or an invented business scheduler. Android may suspend timers;
  /// resume/reconnect always re-arm from the durable SQLite timestamp.
  Future<void> _armOutboxRetry(AppRuntime runtime) async {
    final revision = ++_retryRevision;
    _outboxRetryTimer?.cancel();
    if (!_online) return;
    final processor = runtime.outboxProcessor;
    if (processor == null) return;
    final next = await runtime.outbox?.nextAutomaticRetryAt(
      handledKinds: processor.handlers.keys.toSet(),
    );
    if (!mounted ||
        !_online ||
        revision != _retryRevision ||
        !identical(runtime, widget.runtime) ||
        next == null) {
      return;
    }
    final remaining = next.difference(DateTime.now().toUtc());
    final delay = remaining.isNegative ? const Duration(seconds: 2) : remaining;
    _outboxRetryTimer = Timer(delay, () {
      _outboxRetryTimer = null;
      unawaited(_runDueOutbox(runtime));
    });
  }

  Future<void> _runDueOutbox(AppRuntime runtime) async {
    if (!mounted || !_online || !identical(runtime, widget.runtime)) return;
    try {
      await runtime.outboxProcessor?.run();
    } on Object {
      // The operation itself records its own owner outcome for local readers.
    } finally {
      if (mounted && identical(runtime, widget.runtime)) {
        unawaited(_armOutboxRetry(runtime));
      }
    }
  }

  @override
  void didUpdateWidget(covariant SyncLifecycle oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.runtime, widget.runtime)) {
      _outboxRetryTimer?.cancel();
      _retryRevision++;
      _lastStorageMaintenanceAt = null;
      _maintainedProfile = null;
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
      oldWidget.runtime.sync?.deactivate();
      oldWidget.runtime.outboxProcessor?.deactivate();
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

  /// Cold start and resume upkeep is conservative and fully local.
  /// Never delete a user draft, pending operation or private FileRecord to
  /// satisfy an automatic quota. OS cache cleanup is foreground-only.
  Future<void> _maintainLocalStorage(AppRuntime runtime) async {
    final profileId = runtime.session?.profileId;
    final database = runtime.database;
    if (profileId == null || database == null) return;
    final now = DateTime.now().toUtc();
    final last = _lastStorageMaintenanceAt;
    if (_maintainedProfile == profileId &&
        last != null &&
        !last.isAfter(now) &&
        now.difference(last) < const Duration(hours: 6)) {
      return;
    }
    _maintainedProfile = profileId;
    _lastStorageMaintenanceAt = now;
    try {
      await runtime.store?.purgeExpiredProjections();
    } on Object {
      // Owner snapshots remain usable only under their read-time TTL checks.
    }
    if (!mounted || !identical(runtime, widget.runtime)) return;
    try {
      final staging = await ProfileFileStore.open(
        database: database,
        profileId: profileId,
      );
      await staging.cleanupInterruptedStaging();
      await staging.cleanupInterruptedPrivateCopies();
    } on Object {
      // Staging/Outbox are durable; failure to clean an orphan is harmless.
    }
    if (!mounted || !identical(runtime, widget.runtime)) return;
    try {
      final cache = await ProfileMediaCache.open(profileId);
      await cache.compact();
      await ProfileRecognitionImageStore(profileId: profileId)
          .recoverInterruptedWrites();
    } on Object {
      // Storage pressure never causes deletion of private user bytes.
    }
  }

  Future<void> _refresh() async {
    final sync = widget.runtime.sync;
    final database = widget.runtime.database;
    final profileId = widget.runtime.session?.profileId;
    if (_syncing) {
      // Login/session replacement and connectivity callbacks can overlap the
      // first refresh. Never drop the newer runtime's only acquisition.
      _refreshQueued = true;
      return;
    }
    if (sync == null || database == null || profileId == null) return;
    final runtime = widget.runtime;
    if (mounted) {
      setState(() {
        _syncing = true;
        _syncFailed = false;
      });
    }
    try {
      await _maintainLocalStorage(runtime);
      if (!mounted || !identical(runtime, widget.runtime)) return;
      // The QR vault belongs to this Profile, not to a network response.
      // Expired presentation secrets are removed even if reconnect fails.
      try {
        await SecureAccessCredentialVault().purgeExpiredProfile(profileId);
      } on Object {
        // Secure-store availability must not block nonsecret Now/Me data.
      }
      final rootsSucceeded = await sync.refreshRoots();
      if (!mounted || !identical(runtime, widget.runtime)) return;
      if (rootsSucceeded) {
        // Re-authenticated owner reads permit safe/idempotent 401-paused
        // intentions to resume. No-blind and refetch remain owner-gated.
        await runtime.outbox?.releaseAuthenticatedReplayables();
      }
      // Known Journeys are part of the Profile's durable working set.
      // Prepare their owner projections before entering N3. The screen itself
      // still reads only from ProfileStore; a transport failure cannot hide it.
      await runtime.journeys?.prepareKnownJourneySources(limit: 6);
      // Preparation is a distinct owner. Acquire its metadata into the same
      // Profile database without duplicating it in the Journey projection.
      final ongoing = await runtime.store?.readProjection('personal.ongoing');
      final knownJourneyIds = runtime.preparationResources == null
          ? <String>[]
          : runtime.journeys == null
          ? <String>[]
          : JourneyRepository.knownJourneyIdsFromOngoing(ongoing);
      for (final id in knownJourneyIds) {
        sync.registerPreparedSource(
          runtime.preparationResources!.sourceFor(journeyId: id),
        );
      }
      // A known local Journey also contains authoritative links to its
      // Questionnaires and Requirements. Prepare those owners independently,
      // without ever deriving a mutation permission or copying their data.
      var preparedForms = 0;
      var preparedRequirements = 0;
      for (final journeyId in knownJourneyIds) {
        final localDetail = await runtime.store?.readProjection(
          JourneyRepository.projectionKind,
          resourceKey: journeyId,
        );
        if (runtime.questionnaires != null && preparedForms < 6) {
          final forms = JourneyRepository.knownFormLinksFromDetail(
            localDetail,
            limit: 6 - preparedForms,
          );
          for (final entry in forms.entries) {
            sync.registerPreparedSource(
              runtime.questionnaires!.sourceFor(
                requestId: entry.key,
                detailPath: entry.value,
              ),
            );
            preparedForms++;
          }
        }
        if (runtime.requirements != null && preparedRequirements < 6) {
          final requirements =
              JourneyRepository.knownRequirementLinksFromDetail(
                localDetail,
                journeyId: journeyId,
                limit: 6 - preparedRequirements,
              );
          for (final entry in requirements.entries) {
            sync.registerPreparedSource(
              runtime.requirements!.sourceFor(
                journeyId: journeyId,
                assessmentId: entry.key,
                detailPath: entry.value,
              ),
            );
            preparedRequirements++;
          }
        }
      }
      // Existing collection sources, Journey detail, Preparation, forms and
      // Requirements are all bounded and resume across lifecycle cycles.
      // bounded and resumed on later lifecycle passes.
      final workingSetSucceeded = await sync.refreshPreparedSources(
        maxRequests: 15,
      );
      if (!mounted || !identical(runtime, widget.runtime)) return;
      await _refreshSpaceContextIfNeeded();
      if (!mounted || !identical(runtime, widget.runtime)) return;
      await runtime.outboxProcessor?.run();
      if (mounted && identical(runtime, widget.runtime)) {
        unawaited(_armOutboxRetry(runtime));
      }
      if (mounted && identical(runtime, widget.runtime)) {
        setState(() {
          _syncFailed = !rootsSucceeded || !workingSetSucceeded;
          if (rootsSucceeded && workingSetSucceeded) {
            _lastUpdatedAt = DateTime.now();
          }
        });
      }
    } on MakoloApiError catch (error) {
      if (error.statusCode == 401 && identical(runtime, widget.runtime)) {
        widget.onSessionExpired();
      } else if (mounted && identical(runtime, widget.runtime)) {
        setState(() => _syncFailed = true);
      }
    } on Object {
      if (mounted && identical(runtime, widget.runtime)) {
        setState(() => _syncFailed = true);
      }
    } finally {
      if (mounted) {
        setState(() => _syncing = false);
        if (_refreshQueued || !identical(runtime, widget.runtime)) {
          _refreshQueued = false;
          unawaited(_refresh());
        }
      }
    }
  }

  Future<void> _refreshSpaceContextIfNeeded() async {
    final repository = widget.runtime.space;
    final current = widget.runtime.actorContext?.value;
    if (repository == null || current is! SpaceActorContext) return;

    await repository.refreshInventory();
    final reconciled = widget.runtime.actorContext?.value;
    if (reconciled is SpaceActorContext) {
      await repository.refreshWorkspace(reconciled.space);
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
    // The AppRuntime owns worker lifetime; a temporary shell unmount must
    // not permanently disable an otherwise reusable authenticated runtime.
    WidgetsBinding.instance.removeObserver(this);
    _outboxRetryTimer?.cancel();
    _retryRevision++;
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    unawaited(_connectivity?.cancel());
    unawaited(_outbox?.cancel());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SyncRefreshScope(
    refresh: _refresh,
    child: SyncStatusScope(status: _status, child: widget.child),
  );
}
