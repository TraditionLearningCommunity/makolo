import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/maps/map_runtime_config.dart';
import '../../sync/freshness.dart';
import 'detail_selector.dart';
import 'discovery_mature_view.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';

class DiscoveryScreen extends StatefulWidget {
  const DiscoveryScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;

  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

class _DiscoveryScreenState extends State<DiscoveryScreen> {
  static const _selector = DiscoverySelector();
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readItems(_query);
    final source = await widget.repository.readSource(
      widget.repository.itemsSource(_query),
    );
    if (local == null ||
        DiscoveryRepository.discoveryFreshness.evaluate(
              local,
              now: DateTime.now(),
              invalidated: source.invalidated,
            ) !=
            FreshnessState.fresh) {
      await _refreshItems();
    }
  }

  Future<void> _refreshItems() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(_query);
    } on Object {
      // The existing local snapshot remains usable.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _movePage(int page) {
    if (page < 1) return;
    setState(() => _query = _query.copyWith(page: page));
    unawaited(_acquire());
  }

  void _open(DiscoveryItemPresentation item) {
    if (item.family == 'activity' ||
        item.family == 'service_activity' ||
        item.family == 'funding_activity') {
      widget.onOpenActivity(item.id);
      return;
    }
    widget.onOpenItem(item.family, item.id);
  }

  MakoloReachabilityCue _reachability(DiscoverySourceState source) {
    if (source.reachability == ReachabilityState.unreachable) {
      return MakoloReachabilityCue.temporarilyUnavailable;
    }
    if (source.lastSuccessAt != null) {
      return MakoloReachabilityCue.reachable;
    }
    return MakoloReachabilityCue.unknown;
  }

  @override
  Widget build(BuildContext context) {
    final source = widget.repository.itemsSource(_query);
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchItems(_query),
      builder: (context, snapshot) {
        return StreamBuilder<DiscoverySourceState>(
          stream: widget.repository.watchSource(source),
          initialData: DiscoverySourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = snapshot.data;
            final sourceState =
                sourceSnapshot.data ?? DiscoverySourceState.unknown;
            final freshness = projection == null
                ? FreshnessState.fresh
                : DiscoveryRepository.discoveryFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: sourceState.invalidated,
                  );
            final selection = _selector.select(
              projection: projection,
              hasCriteria: _query.hasCriteria,
              freshness: freshness,
              reachability: _reachability(sourceState),
              failure:
                  sourceState.lastErrorCode != null && projection != null
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing,
            );
            return RefreshIndicator(
              onRefresh: _refreshItems,
              child: DiscoveryExplorationView(
                selection: selection,
                onOpen: _open,
                onPage: _movePage,
                onRetry: () => unawaited(_refreshItems()),
              ),
            );
          },
        );
      },
    );
  }
}

class DiscoverySearchScreen extends StatefulWidget {
  const DiscoverySearchScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
    this.location,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;
  final LocationCapability? location;

  @override
  State<DiscoverySearchScreen> createState() => _DiscoverySearchScreenState();
}

class _DiscoverySearchScreenState extends State<DiscoverySearchScreen> {
  static const _selector = DiscoverySelector();
  final _search = TextEditingController();
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;
  String? _locationMessage;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _submit(String value) async {
    final query = _query.copyWith(text: value, page: 1);
    setState(() {
      _query = query;
      _refreshing = true;
    });
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // Existing results remain visible when refresh fails.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _aroundMe() async {
    final location = widget.location;
    if (location == null) {
      setState(
        () => _locationMessage =
            'La localisation n’est pas disponible sur cet appareil.',
      );
      return;
    }
    final result = await location.current();
    if (!mounted) return;
    if (!result.available || result.fix == null) {
      setState(
        () => _locationMessage =
            'Votre position n’a pas pu être utilisée. '
            'Vous pouvez continuer sans elle.',
      );
      return;
    }
    final query = _query.copyWith(
      latitude: result.fix!.latitude,
      longitude: result.fix!.longitude,
      radiusKm: 25,
      page: 1,
    );
    setState(() {
      _query = query;
      _locationMessage = 'Recherche autour de votre position.';
    });
    await _submit(_search.text);
  }

  void _movePage(int page) {
    if (page < 1) return;
    final query = _query.copyWith(page: page);
    setState(() => _query = query);
    unawaited(_refreshPage(query));
  }

  Future<void> _refreshPage(DiscoveryQuery query) async {
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // Existing results remain visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _open(DiscoveryItemPresentation item) {
    if (item.family == 'activity' ||
        item.family == 'service_activity' ||
        item.family == 'funding_activity') {
      widget.onOpenActivity(item.id);
      return;
    }
    widget.onOpenItem(item.family, item.id);
  }

  void _resetCriteria() {
    _search.clear();
    setState(() {
      _query = const DiscoveryQuery();
      _locationMessage = null;
    });
  }

  MakoloReachabilityCue _reachability(DiscoverySourceState source) {
    if (source.reachability == ReachabilityState.unreachable) {
      return MakoloReachabilityCue.temporarilyUnavailable;
    }
    if (source.lastSuccessAt != null) {
      return MakoloReachabilityCue.reachable;
    }
    return MakoloReachabilityCue.unknown;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Rechercher')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.inner,
              MakoloSpacing.sm,
              MakoloSpacing.inner,
              MakoloSpacing.sm,
            ),
            child: SearchBar(
              key: const Key('discover-search-field'),
              controller: _search,
              autoFocus: true,
              hintText: 'Rechercher une possibilité',
              leading: const Icon(Icons.search_rounded),
              onSubmitted: _submit,
              trailing: [
                IconButton(
                  tooltip: 'Autour de moi',
                  onPressed: _aroundMe,
                  icon: const Icon(Icons.near_me_outlined),
                ),
              ],
            ),
          ),
          if (_locationMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.inner,
              ),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _locationMessage!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
          Expanded(
            child: Builder(
              builder: (context) {
                if (!_query.hasCriteria) {
                  return const Center(
                    child: Text('Saisissez ce que vous recherchez.'),
                  );
                }
                final source = widget.repository.itemsSource(_query);
                return StreamBuilder<StoredProjection?>(
                  stream: widget.repository.watchItems(_query),
                  builder: (context, snapshot) {
                    return StreamBuilder<DiscoverySourceState>(
                      stream: widget.repository.watchSource(source),
                      initialData: DiscoverySourceState.unknown,
                      builder: (context, sourceSnapshot) {
                        final projection = snapshot.data;
                        final sourceState =
                            sourceSnapshot.data ?? DiscoverySourceState.unknown;
                        final freshness = projection == null
                            ? FreshnessState.fresh
                            : DiscoveryRepository.discoveryFreshness.evaluate(
                                projection,
                                now: DateTime.now(),
                                invalidated: sourceState.invalidated,
                              );
                        final selection = _selector.select(
                          projection: projection,
                          hasCriteria: _query.hasCriteria,
                          freshness: freshness,
                          reachability: _reachability(sourceState),
                          failure:
                              sourceState.lastErrorCode != null &&
                                  projection != null
                              ? MakoloFailureCue.recoverable
                              : MakoloFailureCue.none,
                          refreshing: _refreshing,
                        );
                        return RefreshIndicator(
                          onRefresh: () => _refreshPage(_query),
                          child: DiscoveryExplorationView(
                            selection: selection,
                            onOpen: _open,
                            onPage: _movePage,
                            onRetry: () => unawaited(_refreshPage(_query)),
                            onResetCriteria: _resetCriteria,
                          ),
                        );
                      },
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class DiscoveryMapScreen extends StatefulWidget {
  const DiscoveryMapScreen({
    super.key,
    required this.repository,
    required this.mapConfig,
    required this.onOpenOccurrence,
  });

  final DiscoveryRepository repository;
  final MakoloMapsConfig mapConfig;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<DiscoveryMapScreen> createState() => _DiscoveryMapScreenState();
}

class _DiscoveryMapScreenState extends State<DiscoveryMapScreen> {
  static const _selector = DiscoverySelector();
  static const _query = DiscoveryQuery();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readItems(_query);
    if (local == null) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(_query);
    } on Object {
      // Existing Discovery field remains available.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Carte'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchItems(_query),
        builder: (context, snapshot) {
          final selection = _selector.select(
            projection: snapshot.data,
            hasCriteria: _query.hasCriteria,
            refreshing: _refreshing,
          );
          return DiscoverySpatialView(
            selection: selection,
            mapConfig: widget.mapConfig,
            onRetry: () => unawaited(_refresh()),
            onOpen: (item) {
              final occurrenceId = item.occurrenceId;
              if (occurrenceId != null) {
                widget.onOpenOccurrence(occurrenceId);
              }
            },
          );
        },
      ),
    );
  }
}

class DiscoveryItemDetailScreen extends StatefulWidget {
  const DiscoveryItemDetailScreen({
    super.key,
    required this.family,
    required this.id,
    required this.repository,
  });

  final String family;
  final String id;
  final DiscoveryRepository repository;

  @override
  State<DiscoveryItemDetailScreen> createState() =>
      _DiscoveryItemDetailScreenState();
}

class _DiscoveryItemDetailScreenState extends State<DiscoveryItemDetailScreen> {
  static const _selector = DiscoverySelector();
  bool _refreshing = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readItem(widget.family, widget.id);
    if (local == null) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItem(widget.family, widget.id);
    } on Object {
      // Preserve local item if present.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _setSaved(bool saved) async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.setSaved(
        family: widget.family,
        id: widget.id,
        saved: saved,
      );
    } on Object {
      await _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Le changement n’a pas été confirmé. L’état serveur a été relu.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchItem(widget.family, widget.id),
      builder: (context, snapshot) {
        final item = _selector.detail(snapshot.data);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Possibilité'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: item == null
              ? Center(
                  child: _refreshing
                      ? const CircularProgressIndicator()
                      : OutlinedButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: item.eyebrow ?? 'Découvrir',
                      title: item.title,
                      subtitle: item.summary.isEmpty ? null : item.summary,
                      status: item.availability == null
                          ? null
                          : MakoloStatus(label: item.availability!),
                      metadata: [
                        if (item.owner != null)
                          MakoloMetadataItem(
                            item.owner!,
                            icon: Icons.business_outlined,
                          ),
                        if (item.place != null)
                          MakoloMetadataItem(
                            item.place!,
                            icon: Icons.place_outlined,
                          ),
                        if (item.timing != null)
                          MakoloMetadataItem(
                            item.timing!,
                            icon: Icons.schedule_outlined,
                          ),
                        if (item.price != null)
                          MakoloMetadataItem(
                            item.price!,
                            icon: Icons.payments_outlined,
                          ),
                      ],
                    ),
                    if (item.canSave || item.canUnsave)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: MakoloSpacing.inner,
                        ),
                        child: FilledButton.icon(
                          onPressed: _saving
                              ? null
                              : () => _setSaved(item.canSave),
                          icon: Icon(
                            item.canUnsave
                                ? Icons.bookmark_rounded
                                : Icons.bookmark_border_rounded,
                          ),
                          label: Text(
                            item.canUnsave
                                ? 'Retirer des favoris'
                                : 'Enregistrer',
                          ),
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}

class ActivityDetailScreen extends StatefulWidget {
  const ActivityDetailScreen({
    super.key,
    required this.activityId,
    required this.repository,
    required this.onOpenOccurrence,
  });

  final String activityId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<ActivityDetailScreen> createState() => _ActivityDetailScreenState();
}

class _ActivityDetailScreenState extends State<ActivityDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    if (await widget.repository.readActivity(widget.activityId) == null) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshActivity(widget.activityId);
    } on Object {
      // Scoped errors are recorded by SyncSource.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchActivity(widget.activityId),
      builder: (context, snapshot) {
        final activity = _selector.activity(snapshot.data);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Activité'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: activity == null
              ? Center(
                  child: _refreshing
                      ? const CircularProgressIndicator()
                      : OutlinedButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: activity.vertical,
                      title: activity.title,
                      subtitle: activity.summary.isEmpty
                          ? null
                          : activity.summary,
                      status: MakoloStatus(label: activity.state),
                      metadata: [
                        if (activity.owner != null)
                          MakoloMetadataItem(
                            activity.owner!,
                            icon: Icons.business_outlined,
                          ),
                        MakoloMetadataItem(
                          activity.availability,
                          icon: Icons.event_available_outlined,
                        ),
                      ],
                    ),
                    if (activity.occurrences.isNotEmpty)
                      MakoloSection(
                        title: 'Dates et réalisations',
                        child: Column(
                          children: [
                            for (
                              var index = 0;
                              index < activity.occurrences.length;
                              index++
                            ) ...[
                              MakoloCard(
                                onTap: () => widget.onOpenOccurrence(
                                  activity.occurrences[index].id,
                                ),
                                child: MakoloStatusMetadataAction(
                                  title: activity.occurrences[index].label,
                                  status: MakoloStatus(
                                    label: activity.occurrences[index].state,
                                  ),
                                  metadata: [
                                    if (activity.occurrences[index].timing !=
                                        null)
                                      MakoloMetadataItem(
                                        activity.occurrences[index].timing!,
                                        icon: Icons.schedule_outlined,
                                      ),
                                  ],
                                  action: const Icon(
                                    Icons.chevron_right_rounded,
                                  ),
                                ),
                              ),
                              if (index < activity.occurrences.length - 1)
                                const SizedBox(height: MakoloSpacing.sm),
                            ],
                          ],
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}

class OccurrenceDetailScreen extends StatefulWidget {
  const OccurrenceDetailScreen({
    super.key,
    required this.occurrenceId,
    required this.repository,
    required this.onOpenActivity,
    this.onOpenDayOf,
  });

  final String occurrenceId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final VoidCallback? onOpenDayOf;

  @override
  State<OccurrenceDetailScreen> createState() => _OccurrenceDetailScreenState();
}

class _OccurrenceDetailScreenState extends State<OccurrenceDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    if (await widget.repository.readOccurrence(widget.occurrenceId) == null) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshOccurrence(widget.occurrenceId);
    } on Object {
      // Scoped errors are recorded by SyncSource.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchOccurrence(widget.occurrenceId),
      builder: (context, snapshot) {
        final occurrence = _selector.occurrence(snapshot.data);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Occurrence'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: occurrence == null
              ? Center(
                  child: _refreshing
                      ? const CircularProgressIndicator()
                      : OutlinedButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: 'Occurrence',
                      title: occurrence.activityTitle,
                      status: MakoloStatus(label: occurrence.state),
                      metadata: [
                        if (occurrence.timing != null)
                          MakoloMetadataItem(
                            occurrence.timing!,
                            icon: Icons.schedule_outlined,
                          ),
                        if (occurrence.place != null)
                          MakoloMetadataItem(
                            occurrence.place!,
                            icon: Icons.place_outlined,
                          ),
                        MakoloMetadataItem(
                          occurrence.availability,
                          icon: Icons.event_available_outlined,
                        ),
                      ],
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: MakoloSpacing.inner,
                      ),
                      child: OutlinedButton.icon(
                        onPressed: () =>
                            widget.onOpenActivity(occurrence.activityId),
                        icon: const Icon(Icons.arrow_back_rounded),
                        label: const Text('Voir l’activité'),
                      ),
                    ),
                    if (occurrence.canOpenDayOf)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(
                          MakoloSpacing.inner,
                          MakoloSpacing.md,
                          MakoloSpacing.inner,
                          0,
                        ),
                        child: MakoloAttentionBlock(
                          title: 'Jour J disponible',
                          body:
                              'Le serveur indique qu’une profondeur Jour J '
                              'est disponible pour cette occurrence.',
                          icon: Icons.directions_walk_rounded,
                          action: widget.onOpenDayOf == null
                              ? null
                              : FilledButton.icon(
                                  onPressed: widget.onOpenDayOf,
                                  icon: const Icon(
                                    Icons.directions_walk_rounded,
                                  ),
                                  label: const Text('Ouvrir le Jour J'),
                                ),
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}
