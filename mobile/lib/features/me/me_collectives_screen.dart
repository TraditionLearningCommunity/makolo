import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';
import '../../design/makolo_patterns.dart';

import '../../data/local/profile_store.dart';
import '../../navigation/destination.dart';
import '../../network/makolo_api_client.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/sync_status.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/freshness.dart';
import 'me_selector.dart';
import 'me_collectives_content.dart';

/// Owner-backed personal collective relationships, not an authority editor.
class MeCollectivesScreen extends StatefulWidget {
  const MeCollectivesScreen({
    super.key,
    required this.personal,
    required this.api,
    required this.onOpenDestination,
    this.onActSpace,
  });

  final PersonalRepository personal;
  final MakoloApiClient api;
  final bool Function(StructuredDestination destination) onOpenDestination;
  final ValueChanged<MeItemPresentation>? onActSpace;

  @override
  State<MeCollectivesScreen> createState() => _MeCollectivesScreenState();
}

class _MeCollectivesScreenState extends State<MeCollectivesScreen> {
  final ScrollController _scroll = ScrollController();
  late Stream<StoredProjection?> _snapshots;
  StreamSubscription<OwnerSourceState>? _ownerSubscription;
  bool _invalidated = false;
  bool _unreachable = false;
  bool _loading = false;
  bool _failed = false;
  bool _hasMore = false;
  bool _offline = false;
  String? _lastRequested;

  @override
  void initState() {
    super.initState();
    _snapshots = widget.personal.watchMe();
    _bindOwner();
    _scroll.addListener(_checkEnd);
  }

  @override
  void didUpdateWidget(covariant MeCollectivesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.personal != widget.personal) {
      unawaited(_ownerSubscription?.cancel());
      _snapshots = widget.personal.watchMe();
      _invalidated = false;
      _unreachable = false;
      _bindOwner();
      _lastRequested = null;
      _loading = false;
      _failed = false;
      _hasMore = false;
    }
  }

  @override
  void dispose() {
    unawaited(_ownerSubscription?.cancel());
    _scroll.dispose();
    super.dispose();
  }

  void _bindOwner() {
    _ownerSubscription = widget.personal.watchMeSource().listen((source) {
      if (!mounted) return;
      setState(() {
        _invalidated = source.invalidated;
        _unreachable = source.reachability == ReachabilityState.unreachable;
      });
    });
  }

  void _checkEnd() {
    if (!_scroll.hasClients ||
        _scroll.position.extentAfter >= 480 ||
        !_hasMore ||
        _offline ||
        _loading ||
        _failed) {
      return;
    }
    unawaited(_loadNext());
  }

  String _progress(StoredProjection projection) {
    final raw = projection.payload['collectives'];
    if (raw is! Map) return '';
    final offsets = <Object?>[
      for (final family in ['authorized_spaces', 'teams', 'groups'])
        (raw[family] is Map ? (raw[family] as Map)['next_offset'] : null),
    ];
    return '${projection.sourceGeneratedAt?.toIso8601String()}:${offsets.join('/')}';
  }

  Future<void> _loadNext() async {
    if (_loading || _failed || _offline || !_hasMore) return;
    final personal = widget.personal;
    StoredProjection? current;
    try {
      current = await personal.store.readProjection('personal.me');
    } on Object {
      if (mounted && personal == widget.personal) {
        setState(() => _failed = true);
      }
      return;
    }
    if (!mounted || current == null || personal != widget.personal) return;
    final progress = _progress(current);
    if (_lastRequested == progress) return;
    _lastRequested = progress;
    setState(() => _loading = true);
    try {
      await personal.loadMoreMe(
        api: widget.api,
        current: current,
        territory: 'collectives',
      );
      if (!mounted || personal != widget.personal) return;
      setState(() => _failed = false);
    } on Object {
      if (!mounted || personal != widget.personal) return;
      _lastRequested = null;
      setState(() => _failed = true);
    } finally {
      if (mounted && personal == widget.personal) {
        setState(() => _loading = false);
      }
    }
  }

  void _retry() {
    setState(() {
      _failed = false;
      _lastRequested = null;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _checkEnd();
    });
  }

  @override
  Widget build(BuildContext context) {
    _offline =
        _unreachable ||
        SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
    return Scaffold(
      appBar: AppBar(title: const Text('Mes collectifs')),
      body: _invalidated
          ? const Center(
              child: Text('Ces collectifs ne sont plus accessibles.'),
            )
          : StreamBuilder<StoredProjection?>(
              key: ValueKey<String>(
                'me-collectives-scope-${widget.personal.store.profileId}',
              ),
              stream: _snapshots,
              builder: (context, snapshot) {
                final projection = snapshot.data;
                if (projection == null) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const MakoloSkeleton(lines: 3);
                  }
                  return const Center(
                    child: Text('Mes collectifs sont indisponibles.'),
                  );
                }
                final selection = const MeSelector().select(
                  projection: projection,
                  now: DateTime.now().toUtc(),
                );
                final territory = selection.territories.firstWhere(
                  (item) => item.presentation.key == 'collectives',
                );
                _hasMore = territory.hasMore;
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted) _checkEnd();
                });
                return ListView(
                  key: PageStorageKey<String>(
                    'me-collectives-' + widget.personal.store.profileId,
                  ),
                  controller: _scroll,
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 36),
                  children: [
                    MeCollectivesContent(
                      key: ValueKey<String>(
                        'me-collectives-content-' +
                            widget.personal.store.profileId,
                      ),
                      items: territory.items,
                      collectives: projection.payload['collectives'],
                      offline: _offline,
                      hasMore: territory.hasMore,
                      onOpen: widget.onOpenDestination,
                      onActSpace: widget.onActSpace,
                    ),
                    if (_offline && _hasMore)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text('Suite disponible après reconnexion.'),
                      ),
                    if (_loading)
                      const Center(
                        child: Padding(
                          padding: EdgeInsets.all(16),
                          child: CircularProgressIndicator.adaptive(),
                        ),
                      ),
                    if (_failed)
                      Center(
                        child: MakoloActionButton(
                          label: 'Réessayer',
                          onPressed: _retry,
                          appearance: MakoloActionAppearance.quiet,
                        ),
                      ),
                    if (!_loading &&
                        !_failed &&
                        !_offline &&
                        !_hasMore &&
                        territory.items.isNotEmpty)
                      const Padding(
                        padding: EdgeInsets.only(top: 20),
                        child: Center(child: Text('Vous avez tout vu')),
                      ),
                  ],
                );
              },
            ),
    );
  }
}
