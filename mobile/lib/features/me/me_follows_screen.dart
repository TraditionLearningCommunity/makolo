import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';
import '../../design/makolo_patterns.dart';

import '../../data/local/profile_store.dart';
import '../../navigation/destination.dart';
import '../../network/makolo_api_client.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'me_selector.dart';

/// The two follow families remain owned by their existing Profile/Space owners.
class MeFollowsScreen extends StatefulWidget {
  const MeFollowsScreen({
    super.key,
    required this.personal,
    required this.api,
    required this.onOpenDestination,
  });

  final PersonalRepository personal;
  final MakoloApiClient api;
  final bool Function(StructuredDestination destination) onOpenDestination;

  @override
  State<MeFollowsScreen> createState() => _MeFollowsScreenState();
}

class _MeFollowsScreenState extends State<MeFollowsScreen> {
  final ScrollController _scroll = ScrollController();
  late Stream<StoredProjection?> _projections;
  late Stream<OwnerSourceState> _sources;
  bool _loading = false;
  bool _failed = false;
  String? _lastRequest;
  StoredProjection? _current;
  bool _offline = false;

  @override
  void initState() {
    super.initState();
    _bind();
    _scroll.addListener(_checkEnd);
  }

  @override
  void didUpdateWidget(covariant MeFollowsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.personal != oldWidget.personal) {
      _bind();
      _lastRequest = null;
      _current = null;
      _failed = false;
      _loading = false;
    }
  }

  void _bind() {
    _projections = widget.personal.watchMe();
    _sources = widget.personal.watchMeSource();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  String? _pendingFamily(StoredProjection? snapshot) {
    final considerations = snapshot?.payload['considerations'];
    if (considerations is! Map) return null;
    for (final family in ['followed_spaces', 'followed_profiles']) {
      final collection = considerations[family];
      if (collection is Map && collection['has_more'] == true) return family;
    }
    return null;
  }

  void _checkEnd() {
    if (!_scroll.hasClients ||
        _scroll.position.extentAfter >= 480 ||
        _offline ||
        _loading ||
        _failed ||
        _pendingFamily(_current) == null) {
      return;
    }
    unawaited(_next());
  }

  Future<void> _next() async {
    final personal = widget.personal;
    if (_loading || _offline || _failed) return;
    StoredProjection? current;
    try {
      current = await personal.store.readProjection('personal.me');
    } on Object {
      if (mounted && personal == widget.personal) {
        setState(() => _failed = true);
      }
      return;
    }
    if (!mounted || personal != widget.personal || current == null) return;
    final family = _pendingFamily(current);
    if (family == null) return;
    final collection =
        (current.payload['considerations'] as Map)[family] as Map;
    final key =
        '${current.sourceGeneratedAt}:$family:${collection['next_offset']}';
    if (_lastRequest == key) return;
    _lastRequest = key;
    setState(() => _loading = true);
    try {
      await personal.loadMoreMe(
        api: widget.api,
        current: current,
        territory: 'considerations',
        family: family,
      );
      if (!mounted || personal != widget.personal) return;
      setState(() => _failed = false);
    } on Object {
      if (!mounted || personal != widget.personal) return;
      _lastRequest = null;
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
      _lastRequest = null;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _checkEnd();
    });
  }

  @override
  Widget build(BuildContext context) {
    final deviceOffline =
        SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
    return Scaffold(
      appBar: AppBar(title: const Text('Mes suivis')),
      body: StreamBuilder<OwnerSourceState>(
        key: ValueKey<String>(
          'me-follows-scope-${widget.personal.store.profileId}',
        ),
        stream: _sources,
        initialData: OwnerSourceState.unknown,
        builder: (context, sourceSnapshot) {
          final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
          _offline =
              deviceOffline ||
              source.reachability == ReachabilityState.unreachable;
          if (source.invalidated) {
            return const Center(
              child: Text('Ces suivis ne sont plus accessibles.'),
            );
          }
          return StreamBuilder<StoredProjection?>(
            stream: _projections,
            builder: (context, snapshot) {
              final projection = snapshot.data;
              if (projection == null) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const MakoloSkeleton(lines: 3);
                }
                return const Center(
                  child: Text('Mes suivis sont momentanément indisponibles.'),
                );
              }
              _current = projection;
              final selection = const MeSelector().select(
                projection: projection,
                now: DateTime.now().toUtc(),
              );
              final items = selection.territories
                  .firstWhere(
                    (territory) =>
                        territory.presentation.key == 'considerations',
                  )
                  .items;
              final spaces = items
                  .where((item) => item.destination.kind == 'space')
                  .toList();
              final people = items
                  .where((item) => item.destination.kind == 'profile')
                  .toList();
              final pending = _pendingFamily(projection) != null;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) _checkEnd();
              });
              return ListView(
                key: PageStorageKey<String>(
                  'me-followed-${widget.personal.store.profileId}',
                ),
                controller: _scroll,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 36),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  if (spaces.isNotEmpty) ...[
                    Text(
                      'Espaces suivis',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    for (final item in spaces)
                      ListTile(
                        leading: const CircleAvatar(
                          child: Icon(Icons.apartment_rounded),
                        ),
                        title: Text(
                          item.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: item.subtitle == null
                            ? null
                            : Text(
                                item.subtitle!,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                        trailing: item.canOpen
                            ? const Icon(Icons.chevron_right_rounded)
                            : null,
                        onTap: item.canOpen
                            ? () => widget.onOpenDestination(item.destination)
                            : null,
                        onLongPress: () => showMakoloQuickPreview(
                          context,
                          title: item.title,
                          eyebrow: 'Espace suivi',
                          summary: item.subtitle,
                          icon: Icons.apartment_rounded,
                          facts: item.metadata,
                          onOpen: item.canOpen
                              ? () => widget.onOpenDestination(item.destination)
                              : null,
                          actionLabel: 'Ouvrir',
                        ),
                      ),
                  ],
                  if (people.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Personnes suivies',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    for (final item in people)
                      ListTile(
                        leading: const CircleAvatar(
                          child: Icon(Icons.person_outline_rounded),
                        ),
                        title: Text(
                          item.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: item.subtitle == null
                            ? null
                            : Text(
                                item.subtitle!,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                        trailing: item.canOpen
                            ? const Icon(Icons.chevron_right_rounded)
                            : null,
                        onTap: item.canOpen
                            ? () => widget.onOpenDestination(item.destination)
                            : null,
                        onLongPress: () => showMakoloQuickPreview(
                          context,
                          title: item.title,
                          eyebrow: 'Profil suivi',
                          summary: item.subtitle,
                          icon: Icons.person_outline_rounded,
                          facts: item.metadata,
                          onOpen: item.canOpen
                              ? () => widget.onOpenDestination(item.destination)
                              : null,
                          actionLabel: 'Ouvrir',
                        ),
                      ),
                  ],
                  if (spaces.isEmpty && people.isEmpty)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 28),
                      child: Center(
                        child: Text(
                          'Aucune personne ou Espace suivi pour le moment.',
                        ),
                      ),
                    ),
                  if (_offline && pending)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: Text('Suite disponible après reconnexion.'),
                    ),
                  if (_loading)
                    const Padding(
                      padding: EdgeInsets.all(16),
                      child: Center(
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
                  if (!pending &&
                      !_loading &&
                      !_failed &&
                      !_offline &&
                      (spaces.isNotEmpty || people.isNotEmpty))
                    const Padding(
                      padding: EdgeInsets.only(top: 20),
                      child: Center(child: Text('Vous avez tout vu')),
                    ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
